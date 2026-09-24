from datetime import datetime, timezone
from pathlib import Path

from app.repositories.base import IGmailRepository
from app.repositories.sqlite_connection import connect
from app.schemas import GmailConnection

SCHEMA = """
CREATE TABLE IF NOT EXISTS gmail_connection (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    encrypted_refresh_token BLOB NOT NULL,
    connected_at TEXT NOT NULL
);
"""


class SQLiteGmailRepository(IGmailRepository):
    """Stores the single Gmail connection in the same SQLite file as the batches."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self.path) as db:
            db.executescript(SCHEMA)

    def get_gmail_connection(self) -> GmailConnection | None:
        with connect(self.path) as db:
            row = db.execute("SELECT email, connected_at FROM gmail_connection WHERE id = 1").fetchone()
        return GmailConnection(**row) if row else None

    def get_gmail_refresh_token(self) -> bytes | None:
        with connect(self.path) as db:
            row = db.execute(
                "SELECT encrypted_refresh_token FROM gmail_connection WHERE id = 1"
            ).fetchone()
        return row["encrypted_refresh_token"] if row else None

    def save_gmail_connection(self, email: str, encrypted_refresh_token: bytes) -> None:
        with connect(self.path) as db:
            db.execute(
                """
                INSERT OR REPLACE INTO gmail_connection (id, email, encrypted_refresh_token, connected_at)
                VALUES (1, ?, ?, ?)
                """,
                (email, encrypted_refresh_token, datetime.now(timezone.utc).isoformat()),
            )

    def delete_gmail_connection(self) -> None:
        with connect(self.path) as db:
            db.execute("DELETE FROM gmail_connection WHERE id = 1")
