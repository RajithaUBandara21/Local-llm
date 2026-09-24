from pathlib import Path

from app.loaders.base import EmailLoadError, IEmailLoader
from app.loaders.csv_loader import CsvEmailLoader
from app.loaders.mbox_loader import MboxEmailLoader

# The one place that maps a file extension to a loader; a new format adds one entry here.
_LOADERS: dict[str, type[IEmailLoader]] = {
    ".mbox": MboxEmailLoader,
    ".csv": CsvEmailLoader,
}

SUPPORTED_MAILBOX_EXTENSIONS = frozenset(_LOADERS)


def get_email_loader(path: Path) -> IEmailLoader:
    loader_class = _LOADERS.get(path.suffix.lower())
    if loader_class is None:
        supported = ", ".join(sorted(_LOADERS))
        raise EmailLoadError(f"Unsupported mailbox file type {path.suffix!r}; supported: {supported}.")
    return loader_class()
