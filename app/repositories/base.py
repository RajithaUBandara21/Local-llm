from abc import ABC, abstractmethod

from app.schemas import (
    Agent, BatchStatus, LoadedEmail, MailboxEmail, ReviewAction, ReviewActionType, Seed, StoredEmail, TriageResponse,
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
    def list_mailbox_emails(self, mailbox: str, batch_id: int | None = None) -> list[MailboxEmail]:
        """Emails of one mailbox in email id order, each with its stored result or none."""

    @abstractmethod
    def get_email(self, email_id: int) -> MailboxEmail | None:
        """One email with its stored triage result and latest review action, or None if it does not exist."""

    @abstractmethod
    def save_review_action(
        self, email_id: int, agent_id: str, action: ReviewActionType, edited_reply: str | None
    ) -> ReviewAction:
        """Append one review action for the email and return it; earlier actions are kept."""


class IAccessRepository(ABC):
    """Abstract interface for the agent directory, mailbox assignments, and denial log."""

    @abstractmethod
    def replace_directory(self, seed: Seed) -> None:
        """Replace all agents and assignments at once; the denial log is kept."""

    @abstractmethod
    def list_agents(self) -> list[Agent]: pass

    @abstractmethod
    def get_agent(self, agent_id: str) -> Agent | None: pass

    @abstractmethod
    def mailboxes_for(self, agent_id: str) -> list[str]: pass

    @abstractmethod
    def is_assigned(self, agent_id: str, mailbox: str) -> bool: pass

    @abstractmethod
    def log_denial(self, agent_id: str, mailbox: str, reason: str) -> None: pass
