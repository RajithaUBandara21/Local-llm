from abc import ABC, abstractmethod

from app.schemas import BatchStatus, LoadedEmail, StoredEmail, TriageResponse


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
