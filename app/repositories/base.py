from abc import ABC, abstractmethod

from app.schemas import (
    BatchStatus, GmailConnection, LoadedEmail, ReviewableEmail, ReviewAction, ReviewActionType, StoredEmail,
    TriageResponse,
)


class IMetricsRepository(ABC):
    """Abstract interface for reading benchmark metrics."""

    @abstractmethod
    def get_latest_metrics(self) -> dict: pass


class IBatchRepository(ABC):
    """Abstract interface for storing batches, their emails, and triage results."""

    @abstractmethod
    def create_batch(self, source_file: str, emails: list[LoadedEmail]) -> int:
        """Store a running batch with its emails and return the batch id."""

    @abstractmethod
    def get_batch(self, batch_id: int) -> BatchStatus | None: pass

    @abstractmethod
    def list_batches(self) -> list[BatchStatus]:
        """Newest batch first."""

    @abstractmethod
    def pending_emails(self, batch_id: int) -> list[StoredEmail]:
        """Emails of the batch with no stored result yet, in file order."""

    @abstractmethod
    def save_result(self, email_id: int, response: TriageResponse) -> None:
        """Store the result and its decision-log row together, replacing an earlier result."""

    @abstractmethod
    def mark_completed(self, batch_id: int) -> None: pass

    @abstractmethod
    def list_emails(self, batch_id: int | None = None) -> list[ReviewableEmail]:
        """Every stored email in id order, each with its stored result or none."""

    @abstractmethod
    def get_email(self, email_id: int) -> ReviewableEmail | None:
        """One email with its stored triage result and latest review action, or None if it does not exist."""

    @abstractmethod
    def save_review_action(self, email_id: int, action: ReviewActionType, edited_reply: str | None) -> ReviewAction:
        """Append one review action for the email and return it; earlier actions are kept."""

    @abstractmethod
    def delete_batch(self, batch_id: int) -> None:
        """Delete the batch and every row that depends on it; a no-op when the batch does not exist."""


class IGmailRepository(ABC):
    """Abstract interface for the single stored Gmail connection."""

    @abstractmethod
    def get_gmail_connection(self) -> GmailConnection | None:
        """The single stored Gmail connection, or None if never connected."""

    @abstractmethod
    def get_gmail_refresh_token(self) -> bytes | None:
        """The single stored connection's encrypted refresh token, or None if never connected."""

    @abstractmethod
    def save_gmail_connection(self, email: str, encrypted_refresh_token: bytes) -> None:
        """Replace the single stored Gmail connection with a fresh connected_at."""

    @abstractmethod
    def delete_gmail_connection(self) -> None:
        """Remove the stored Gmail connection; a no-op if none exists."""
