from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas import LoadedEmail


class EmailLoadError(Exception):
    """A mailbox file could not be loaded; the message says what to fix."""


class IEmailLoader(ABC):
    """Abstract interface for reading a mailbox file into cleaned emails."""

    @abstractmethod
    def load(self, path: Path) -> list[LoadedEmail]: pass
