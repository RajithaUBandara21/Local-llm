import json
from datetime import datetime, timezone
from pathlib import Path

from app.repositories.base import IBatchRepository
from app.repositories.sqlite_connection import connect
from app.schemas import (
    BatchStatus, LoadedEmail, PendingMailboxFile, ReviewableEmail, ReviewAction, ReviewActionType, StoredEmail,
    TriageResponse, TriageResult,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    total INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed')),
    created_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    sender TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_clean TEXT NOT NULL,
    received_at TEXT
);
CREATE INDEX IF NOT EXISTS emails_batch_id ON emails(batch_id);
CREATE TABLE IF NOT EXISTS triage_results (
    email_id INTEGER PRIMARY KEY REFERENCES emails(id),
    model TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'needs_review', 'failed')),
    attempts INTEGER NOT NULL,
    latency_sec REAL NOT NULL,
    category TEXT,
    priority TEXT,
    summary TEXT,
    suggested_reply TEXT,
    confidence REAL,
    flags TEXT,
    flag_reason TEXT,
    failure_reason TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL REFERENCES emails(id),
    model TEXT NOT NULL,
    latency_sec REAL NOT NULL,
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- Append-only, like decision_log: every review decision is kept, never overwritten.
CREATE TABLE IF NOT EXISTS review_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL REFERENCES emails(id),
    action TEXT NOT NULL CHECK (action IN ('approve', 'edit', 'reject')),
    edited_reply TEXT,
    created_at TEXT NOT NULL
);
-- An uploaded mailbox file with no batch started from it yet; its row is deleted once one is,
-- so a mail set's chosen name survives a page refresh up to that point.
CREATE TABLE IF NOT EXISTS mailbox_files (
    file TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Counts come from the results themselves, so a resume can never leave a counter out of step.
BATCH_QUERY = """
SELECT b.id, b.source_file, b.display_name, b.status, b.total, b.created_at, b.finished_at,
       COUNT(r.email_id) AS processed,
       COALESCE(SUM(r.status = 'ok'), 0) AS ok,
       COALESCE(SUM(r.status = 'needs_review'), 0) AS needs_review,
       COALESCE(SUM(r.status = 'failed'), 0) AS failed
FROM batches b
LEFT JOIN emails e ON e.batch_id = b.id
LEFT JOIN triage_results r ON r.email_id = e.id
{where}
GROUP BY b.id
ORDER BY b.id DESC
"""


# Shared by both the full listing and a single-email read, so the row shape and its mapper stay one thing.
# The correlated subquery picks each email's highest-id review action; a plain SQLite join keeps it
# portable rather than relying on window functions.
EMAIL_SELECT = """
SELECT e.id, e.batch_id, e.sender, e.subject, e.body_clean, e.received_at,
       r.status, r.model, r.attempts, r.latency_sec, r.category, r.priority, r.summary,
       r.suggested_reply, r.confidence, r.flags, r.flag_reason, r.failure_reason,
       rv.id AS review_id, rv.action AS review_action,
       rv.edited_reply AS review_edited_reply, rv.created_at AS review_created_at
FROM emails e
LEFT JOIN triage_results r ON r.email_id = e.id
LEFT JOIN review_actions rv ON rv.id = (SELECT MAX(id) FROM review_actions WHERE email_id = e.id)
"""

ALL_EMAILS_QUERY = EMAIL_SELECT + "{batch_filter} ORDER BY e.id"
# {batch_filter} is either "" or "WHERE e.batch_id = ?"; kept as a named slot so the query reads
# the same whether or not a batch id narrows it.

EMAIL_BY_ID_QUERY = EMAIL_SELECT + "WHERE e.id = ?"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _review_action(row) -> ReviewAction | None:
    if row["review_id"] is None:
        return None
    return ReviewAction(
        id=row["review_id"], email_id=row["id"],
        action=row["review_action"], edited_reply=row["review_edited_reply"], created_at=row["review_created_at"],
    )


def _reviewable_email(row) -> ReviewableEmail:
    triage = None
    if row["status"] is not None:
        result = None
        if row["status"] == "ok":
            result = TriageResult(
                category=row["category"], priority=row["priority"], summary=row["summary"],
                suggested_reply=row["suggested_reply"], confidence=row["confidence"],
                flags=json.loads(row["flags"]), flag_reason=row["flag_reason"],
            )
        triage = TriageResponse(
            status=row["status"], model=row["model"], attempts=row["attempts"],
            latency_sec=row["latency_sec"], result=result, failure_reason=row["failure_reason"],
        )
    return ReviewableEmail(
        id=row["id"], batch_id=row["batch_id"], sender=row["sender"],
        subject=row["subject"], body_clean=row["body_clean"], received_at=row["received_at"], triage=triage,
        review=_review_action(row),
    )


class SQLiteBatchRepository(IBatchRepository):
    """Stores batches in one SQLite file, opening a connection per call so threads never share one."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self.path) as db:
            db.executescript(SCHEMA)
            # Added after the initial release; a database created before it existed needs this
            # column added on top of the CREATE TABLE above, which only runs for a new database.
            columns = {row["name"] for row in db.execute("PRAGMA table_info(batches)")}
            if "display_name" not in columns:
                db.execute("ALTER TABLE batches ADD COLUMN display_name TEXT")
                db.execute("UPDATE batches SET display_name = source_file WHERE display_name IS NULL")

    def create_batch(self, source_file: str, emails: list[LoadedEmail]) -> int:
        rows = [
            (
                email.sender, email.subject, email.body_clean,
                email.received_at.isoformat() if email.received_at else None,
            )
            for email in emails
        ]
        with connect(self.path) as db:
            # Carry over the name chosen when the file was uploaded, if any, so a mail set keeps
            # its display name once it becomes a batch instead of falling back to the raw filename.
            pending = db.execute(
                "SELECT display_name FROM mailbox_files WHERE file = ?", (source_file,)
            ).fetchone()
            display_name = pending["display_name"] if pending else source_file
            cursor = db.execute(
                "INSERT INTO batches (source_file, display_name, total, status, created_at) "
                "VALUES (?, ?, ?, 'running', ?)",
                (source_file, display_name, len(emails), _now()),
            )
            batch_id = cursor.lastrowid
            db.executemany(
                "INSERT INTO emails (batch_id, sender, subject, body_clean, received_at) VALUES (?, ?, ?, ?, ?)",
                [(batch_id, *row) for row in rows],
            )
            # The file has a batch now, so it is no longer a pending upload.
            db.execute("DELETE FROM mailbox_files WHERE file = ?", (source_file,))
        return batch_id

    def save_pending_mailbox_file(self, file: str, display_name: str) -> None:
        with connect(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO mailbox_files (file, display_name, created_at) VALUES (?, ?, ?)",
                (file, display_name, _now()),
            )

    def list_pending_mailbox_files(self) -> list[PendingMailboxFile]:
        with connect(self.path) as db:
            rows = db.execute(
                "SELECT file, display_name, created_at FROM mailbox_files ORDER BY created_at DESC"
            ).fetchall()
        return [PendingMailboxFile(**row) for row in rows]

    def delete_pending_mailbox_file(self, file: str) -> None:
        with connect(self.path) as db:
            db.execute("DELETE FROM mailbox_files WHERE file = ?", (file,))

    def get_batch(self, batch_id: int) -> BatchStatus | None:
        with connect(self.path) as db:
            row = db.execute(BATCH_QUERY.format(where="WHERE b.id = ?"), (batch_id,)).fetchone()
        return BatchStatus(**row) if row else None

    def list_batches(self, limit: int | None = None, offset: int = 0) -> list[BatchStatus]:
        sql = BATCH_QUERY.format(where="")
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = (limit, offset)
        with connect(self.path) as db:
            rows = db.execute(sql, params).fetchall()
        return [BatchStatus(**row) for row in rows]

    def pending_emails(self, batch_id: int) -> list[StoredEmail]:
        with connect(self.path) as db:
            rows = db.execute(
                "SELECT e.id, e.sender, e.subject, e.body_clean, e.received_at FROM emails e "
                "LEFT JOIN triage_results r ON r.email_id = e.id "
                "WHERE e.batch_id = ? AND r.email_id IS NULL ORDER BY e.id",
                (batch_id,),
            ).fetchall()
        return [StoredEmail(**row) for row in rows]

    def save_result(self, email_id: int, response: TriageResponse) -> None:
        result = response.result
        now = _now()
        with connect(self.path) as db:
            db.execute(
                "INSERT OR REPLACE INTO triage_results (email_id, model, status, attempts, latency_sec, "
                "category, priority, summary, suggested_reply, confidence, flags, flag_reason, "
                "failure_reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    email_id, response.model, response.status, response.attempts, response.latency_sec,
                    result.category if result else None,
                    result.priority if result else None,
                    result.summary if result else None,
                    result.suggested_reply if result else None,
                    result.confidence if result else None,
                    json.dumps(result.flags) if result else None,
                    result.flag_reason if result else None,
                    response.failure_reason, now,
                ),
            )
            db.execute(
                "INSERT INTO decision_log (email_id, model, latency_sec, outcome, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (email_id, response.model, response.latency_sec, response.status, now),
            )

    def mark_completed(self, batch_id: int) -> None:
        with connect(self.path) as db:
            db.execute(
                "UPDATE batches SET status = 'completed', finished_at = ? WHERE id = ?", (_now(), batch_id)
            )

    def list_emails(
        self, batch_id: int | None = None, limit: int | None = None, offset: int = 0
    ) -> list[ReviewableEmail]:
        sql = ALL_EMAILS_QUERY.format(batch_filter="" if batch_id is None else "WHERE e.batch_id = ?")
        params = () if batch_id is None else (batch_id,)
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = (*params, limit, offset)
        with connect(self.path) as db:
            rows = db.execute(sql, params).fetchall()
        return [_reviewable_email(row) for row in rows]

    def get_email(self, email_id: int) -> ReviewableEmail | None:
        with connect(self.path) as db:
            row = db.execute(EMAIL_BY_ID_QUERY, (email_id,)).fetchone()
        return _reviewable_email(row) if row else None

    def save_review_action(self, email_id: int, action: ReviewActionType, edited_reply: str | None) -> ReviewAction:
        now = _now()
        with connect(self.path) as db:
            cursor = db.execute(
                "INSERT INTO review_actions (email_id, action, edited_reply, created_at) VALUES (?, ?, ?, ?)",
                (email_id, action, edited_reply, now),
            )
            review_id = cursor.lastrowid
        return ReviewAction(id=review_id, email_id=email_id, action=action, edited_reply=edited_reply, created_at=now)

    def delete_batch(self, batch_id: int) -> None:
        with connect(self.path) as db:
            db.execute(
                "DELETE FROM review_actions WHERE email_id IN (SELECT id FROM emails WHERE batch_id = ?)",
                (batch_id,),
            )
            db.execute(
                "DELETE FROM decision_log WHERE email_id IN (SELECT id FROM emails WHERE batch_id = ?)",
                (batch_id,),
            )
            db.execute(
                "DELETE FROM triage_results WHERE email_id IN (SELECT id FROM emails WHERE batch_id = ?)",
                (batch_id,),
            )
            db.execute("DELETE FROM emails WHERE batch_id = ?", (batch_id,))
            db.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
