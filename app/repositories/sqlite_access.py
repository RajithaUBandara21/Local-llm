from datetime import datetime, timezone
from pathlib import Path

from app.repositories.base import IAccessRepository
from app.repositories.sqlite_connection import connect
from app.schemas import Agent, GmailConnection, Seed

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mailboxes (
    name TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS mailbox_assignments (
    agent_id TEXT NOT NULL REFERENCES agents(id),
    mailbox TEXT NOT NULL,
    PRIMARY KEY (agent_id, mailbox)
);
-- agent_id is deliberately not a foreign key, so a denial is never lost when the directory is replaced.
CREATE TABLE IF NOT EXISTS access_denials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    mailbox TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gmail_connection (
    id INTEGER PRIMARY KEY,
    mailbox TEXT NOT NULL,
    email TEXT NOT NULL,
    encrypted_refresh_token BLOB NOT NULL,
    connected_at TEXT NOT NULL
);
"""


class SQLiteAccessRepository(IAccessRepository):
    """Stores the agent directory and the denial log in the same SQLite file as the batches."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self.path) as db:
            db.executescript(SCHEMA)

    def replace_directory(self, seed: Seed) -> None:
        with connect(self.path) as db:
            db.execute("DELETE FROM mailbox_assignments")
            db.execute("DELETE FROM agents")
            db.execute("DELETE FROM mailboxes")
            db.executemany("INSERT INTO agents (id, name) VALUES (?, ?)", [(a.id, a.name) for a in seed.agents])
            db.executemany(
                "INSERT INTO mailboxes (name) VALUES (?)", [(mailbox,) for mailbox in seed.assignments]
            )
            db.executemany(
                "INSERT INTO mailbox_assignments (agent_id, mailbox) VALUES (?, ?)",
                [(agent_id, mailbox) for mailbox, agent_ids in seed.assignments.items() for agent_id in agent_ids],
            )

    def list_agents(self) -> list[Agent]:
        with connect(self.path) as db:
            rows = db.execute("SELECT id, name FROM agents ORDER BY id").fetchall()
        return [Agent(**row) for row in rows]

    def get_agent(self, agent_id: str) -> Agent | None:
        with connect(self.path) as db:
            row = db.execute("SELECT id, name FROM agents WHERE id = ?", (agent_id,)).fetchone()
        return Agent(**row) if row else None

    def mailboxes_for(self, agent_id: str) -> list[str]:
        with connect(self.path) as db:
            rows = db.execute(
                "SELECT mailbox FROM mailbox_assignments WHERE agent_id = ? ORDER BY mailbox", (agent_id,)
            ).fetchall()
        return [row["mailbox"] for row in rows]

    def is_assigned(self, agent_id: str, mailbox: str) -> bool:
        with connect(self.path) as db:
            row = db.execute(
                "SELECT 1 FROM mailbox_assignments WHERE agent_id = ? AND mailbox = ?", (agent_id, mailbox)
            ).fetchone()
        return row is not None

    def log_denial(self, agent_id: str, mailbox: str, reason: str) -> None:
        with connect(self.path) as db:
            db.execute(
                "INSERT INTO access_denials (agent_id, mailbox, reason, created_at) VALUES (?, ?, ?, ?)",
                (agent_id, mailbox, reason, datetime.now(timezone.utc).isoformat()),
            )

    def list_mailboxes(self) -> list[str]:
        with connect(self.path) as db:
            rows = db.execute("SELECT name FROM mailboxes ORDER BY name").fetchall()
        return [row["name"] for row in rows]

    def create_mailbox(self, name: str) -> None:
        with connect(self.path) as db:
            db.execute("INSERT INTO mailboxes (name) VALUES (?)", (name,))

    def delete_mailbox(self, name: str) -> None:
        with connect(self.path) as db:
            db.execute("DELETE FROM mailbox_assignments WHERE mailbox = ?", (name,))
            db.execute("DELETE FROM mailboxes WHERE name = ?", (name,))

    def create_agent(self, agent: Agent) -> None:
        with connect(self.path) as db:
            db.execute("INSERT INTO agents (id, name) VALUES (?, ?)", (agent.id, agent.name))

    def rename_agent(self, agent_id: str, name: str) -> Agent:
        with connect(self.path) as db:
            cursor = db.execute("UPDATE agents SET name = ? WHERE id = ?", (name, agent_id))
            if cursor.rowcount == 0:
                raise KeyError(agent_id)
        return Agent(id=agent_id, name=name)

    def delete_agent(self, agent_id: str) -> None:
        with connect(self.path) as db:
            db.execute("DELETE FROM mailbox_assignments WHERE agent_id = ?", (agent_id,))
            db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))

    def assign(self, agent_id: str, mailbox: str) -> None:
        with connect(self.path) as db:
            # Both sides must exist, or the insert either violates the agent foreign key (agent_id)
            # or creates a phantom row for a mailbox nobody can see (mailbox has no such key); a
            # missing target is treated the same as delete/unassign's existing no-op contract.
            agent_exists = db.execute("SELECT 1 FROM agents WHERE id = ?", (agent_id,)).fetchone()
            mailbox_exists = db.execute("SELECT 1 FROM mailboxes WHERE name = ?", (mailbox,)).fetchone()
            if not agent_exists or not mailbox_exists:
                return
            db.execute(
                "INSERT OR IGNORE INTO mailbox_assignments (agent_id, mailbox) VALUES (?, ?)", (agent_id, mailbox)
            )

    def unassign(self, agent_id: str, mailbox: str) -> None:
        with connect(self.path) as db:
            db.execute(
                "DELETE FROM mailbox_assignments WHERE agent_id = ? AND mailbox = ?", (agent_id, mailbox)
            )

    def get_gmail_connection(self) -> GmailConnection | None:
        with connect(self.path) as db:
            row = db.execute(
                "SELECT mailbox, email, connected_at FROM gmail_connection WHERE id = 1"
            ).fetchone()
        return GmailConnection(**row) if row else None

    def get_gmail_refresh_token(self) -> bytes | None:
        with connect(self.path) as db:
            row = db.execute(
                "SELECT encrypted_refresh_token FROM gmail_connection WHERE id = 1"
            ).fetchone()
        return row["encrypted_refresh_token"] if row else None

    def save_gmail_connection(self, mailbox: str, email: str, encrypted_refresh_token: bytes) -> None:
        with connect(self.path) as db:
            db.execute(
                """
                INSERT OR REPLACE INTO gmail_connection
                    (id, mailbox, email, encrypted_refresh_token, connected_at)
                VALUES (1, ?, ?, ?, ?)
                """,
                (mailbox, email, encrypted_refresh_token, datetime.now(timezone.utc).isoformat()),
            )

    def delete_gmail_connection(self) -> None:
        with connect(self.path) as db:
            db.execute("DELETE FROM gmail_connection WHERE id = 1")
