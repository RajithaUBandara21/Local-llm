import csv
from datetime import datetime
from pathlib import Path

from app.loaders.base import EmailLoadError, IEmailLoader
from app.loaders.cleaner import clean_body, looks_like_html
from app.schemas import LoadedEmail

REQUIRED_COLUMNS = ("sender", "subject", "body", "received_at")


class CsvEmailLoader(IEmailLoader):
    """Loads emails from a UTF-8 CSV with sender, subject, body, and received_at columns."""

    def load(self, path: Path) -> list[LoadedEmail]:
        try:
            # utf-8-sig drops the BOM Excel adds, which would otherwise stick to the first header.
            with path.open(encoding="utf-8-sig", newline="") as file:
                return self._read_rows(csv.DictReader(file))
        except FileNotFoundError:
            raise EmailLoadError(f"CSV file not found: {path}") from None
        except UnicodeDecodeError:
            raise EmailLoadError(f"CSV file is not valid UTF-8: {path}") from None
        except (OSError, csv.Error) as error:
            raise EmailLoadError(f"Could not read CSV file {path}: {error}") from error

    def _read_rows(self, reader: csv.DictReader) -> list[LoadedEmail]:
        if reader.fieldnames is None:
            raise EmailLoadError("CSV file is empty; it needs a header row.")
        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise EmailLoadError(f"CSV file is missing required columns: {', '.join(missing)}.")
        return [self._to_email(row, number) for number, row in enumerate(reader, start=1)]

    @staticmethod
    def _to_email(row: dict, number: int) -> LoadedEmail:
        # A short row leaves later cells as None, so every read falls back to "".
        cell = {name: (value or "").strip() for name, value in row.items() if name is not None}
        try:
            received_at = datetime.fromisoformat(cell["received_at"]) if cell["received_at"] else None
        except ValueError:
            raise EmailLoadError(
                f"CSV row {number} has an invalid received_at {cell['received_at']!r}; use ISO 8601, "
                "for example 2026-03-02T09:15:00+00:00."
            ) from None
        body = row.get("body") or ""
        return LoadedEmail(
            sender=cell["sender"],
            subject=cell["subject"],
            body_clean=clean_body(body, is_html=looks_like_html(body)),
            received_at=received_at,
            mailbox=cell.get("mailbox") or None,
        )
