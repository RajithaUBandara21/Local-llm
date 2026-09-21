import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.repositories.base import IBatchRepository
from app.schemas import BatchStatus, LoadedEmail, StoredEmail, TriageResponse

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
    mailbox TEXT,
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
"""

# Counts come from the results themselves, so a resume can never leave a counter out of step.
BATCH_QUERY = """
SELECT b.id, b.source_file, b.status, b.total, b.created_at, b.finished_at,
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteBatchRepository(IBatchRepository):
    """Stores batches in one SQLite file, opening a connection per call so threads never share one."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # A long timeout lets a status read wait out the worker's short write transactions.
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                yield connection
        finally:
            connection.close()

    def create_batch(self, source_file: str, emails: list[LoadedEmail]) -> int:
        rows = [
            (
                email.mailbox, email.sender, email.subject, email.body_clean,
                email.received_at.isoformat() if email.received_at else None,
            )
            for email in emails
        ]
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO batches (source_file, total, status, created_at) VALUES (?, ?, 'running', ?)",
                (source_file, len(emails), _now()),
            )
            batch_id = cursor.lastrowid
            db.executemany(
                "INSERT INTO emails (batch_id, mailbox, sender, subject, body_clean, received_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(batch_id, *row) for row in rows],
            )
        return batch_id

    def get_batch(self, batch_id: int) -> BatchStatus | None:
        with self._connect() as db:
            row = db.execute(BATCH_QUERY.format(where="WHERE b.id = ?"), (batch_id,)).fetchone()
        return BatchStatus(**row) if row else None

    def list_batches(self) -> list[BatchStatus]:
        with self._connect() as db:
            rows = db.execute(BATCH_QUERY.format(where="")).fetchall()
        return [BatchStatus(**row) for row in rows]

    def pending_emails(self, batch_id: int) -> list[StoredEmail]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT e.id, e.mailbox, e.sender, e.subject, e.body_clean, e.received_at FROM emails e "
                "LEFT JOIN triage_results r ON r.email_id = e.id "
                "WHERE e.batch_id = ? AND r.email_id IS NULL ORDER BY e.id",
                (batch_id,),
            ).fetchall()
        return [StoredEmail(**row) for row in rows]

    def save_result(self, email_id: int, response: TriageResponse) -> None:
        result = response.result
        now = _now()
        with self._connect() as db:
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
        with self._connect() as db:
            db.execute(
                "UPDATE batches SET status = 'completed', finished_at = ? WHERE id = ?", (_now(), batch_id)
            )
