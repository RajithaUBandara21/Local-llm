from datetime import datetime, timezone
from pathlib import Path

from app.repositories.base import IAccessRepository
from app.repositories.sqlite_connection import connect
from app.schemas import Agent, Seed

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
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
            db.executemany("INSERT INTO agents (id, name) VALUES (?, ?)", [(a.id, a.name) for a in seed.agents])
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
