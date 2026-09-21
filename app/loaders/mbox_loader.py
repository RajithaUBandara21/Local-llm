import email
import email.errors
import email.policy
import email.utils
import mailbox
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import BinaryIO

from app.loaders.base import EmailLoadError, IEmailLoader
from app.loaders.cleaner import clean_body
from app.schemas import LoadedEmail

# LookupError covers a charset name Python does not know; UnicodeError is a ValueError.
_MESSAGE_ERRORS = (LookupError, ValueError, email.errors.MessageError)


def _parse_message(file: BinaryIO) -> EmailMessage:
    # The default policy decodes encoded-word headers and gives get_body/get_content.
    return email.message_from_binary_file(file, policy=email.policy.default)


class MboxEmailLoader(IEmailLoader):
    """Loads emails from a standard mbox file, one per message in file order."""

    def load(self, path: Path) -> list[LoadedEmail]:
        try:
            box = mailbox.mbox(path, factory=_parse_message, create=False)
        except mailbox.NoSuchMailboxError:
            raise EmailLoadError(f"mbox file not found: {path}") from None
        except (OSError, mailbox.Error) as error:
            raise EmailLoadError(f"Could not open mbox file {path}: {error}") from error
        try:
            emails = [self._read_message(box, key, number) for number, key in enumerate(box.keys(), start=1)]
        except (OSError, mailbox.Error) as error:
            raise EmailLoadError(f"Could not read mbox file {path}: {error}") from error
        finally:
            box.close()
        if not emails and path.stat().st_size > 0:
            raise EmailLoadError(f"No messages found in {path}; is it an mbox file?")
        return emails

    def _read_message(self, box: mailbox.mbox, key: int, number: int) -> LoadedEmail:
        try:
            return self._to_email(box[key], number)
        except _MESSAGE_ERRORS as error:
            raise EmailLoadError(f"mbox message {number} could not be read: {error}") from error

    @staticmethod
    def _to_email(message: EmailMessage, number: int) -> LoadedEmail:
        return LoadedEmail(
            sender=str(message.get("From", "")).strip(),
            subject=str(message.get("Subject", "")).strip(),
            body_clean=MboxEmailLoader._body(message),
            received_at=MboxEmailLoader._received_at(message, number),
            mailbox=None,
        )

    @staticmethod
    def _received_at(message: EmailMessage, number: int) -> datetime | None:
        raw = str(message.get("Date", "")).strip()
        if not raw:
            return None
        try:
            return email.utils.parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            raise EmailLoadError(f"mbox message {number} has an unparseable Date header: {raw!r}") from None

    @staticmethod
    def _body(message: EmailMessage) -> str:
        part = message.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        return clean_body(part.get_content(), is_html=part.get_content_subtype() == "html")
