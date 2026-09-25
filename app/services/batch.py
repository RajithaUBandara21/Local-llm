import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from app.config import MAX_MAILBOX_UPLOAD_BYTES
from app.loaders.base import EmailLoadError
from app.loaders.factory import SUPPORTED_MAILBOX_EXTENSIONS, get_email_loader
from app.repositories.base import IBatchRepository
from app.schemas import (
    BatchStatus, LoadedEmail, MailboxFilePreview, MailboxFileUpload, PendingMailboxFile, ReviewableEmail,
    ReviewAction, ReviewActionType, StoredEmail, TriageRequest, TriageResponse,
)
from app.services.triage import TriageService
from app.state import AppState

logger = logging.getLogger(__name__)

# Matches the frontend mock's batch size (web/lib/constants.ts MOCK_BATCH_SIZE),
# so the real bulk-insert produces the same shape the client used to fake.
BULK_INSERT_SIZE = 10


class BatchService:
    """Stores a mailbox file as a batch and triages its emails one at a time, resumably."""

    def __init__(self, repository: IBatchRepository, triage: TriageService, state: AppState, mailbox_dir: Path):
        self.repository = repository
        self.triage = triage
        self.state = state
        self.mailbox_dir = mailbox_dir

    def start(self, file_name: str) -> BatchStatus:
        # Routes run in a thread pool, and loading a file takes long enough for two overlapping
        # requests to both pass a bare check, so the check and the claim share one lock.
        with self.state.batch_lock:
            self._ensure_idle()
            path = self._resolve(file_name)
            try:
                emails = get_email_loader(path).load(path)
            except EmailLoadError as error:
                raise HTTPException(status_code=400, detail=str(error))
            if not emails:
                raise HTTPException(status_code=400, detail=f"{file_name} contains no emails.")
            batch_id = self.repository.create_batch(path.name, emails)
            self.state.active_batch_id = batch_id
        return self.get(batch_id)

    def bulk_insert(self) -> BatchStatus:
        with self.state.batch_lock:
            self._ensure_idle()
            source_file = f"test:{datetime.now(timezone.utc).isoformat()}"
            batch_id = self.repository.create_batch(source_file, self._synthetic_emails())
            self.state.active_batch_id = batch_id
        return self.get(batch_id)

    def delete(self, batch_id: int) -> None:
        batch = self.get(batch_id)  # raises 404 when the batch does not exist
        with self.state.batch_lock:
            if self.state.active_batch_id == batch_id:
                raise HTTPException(status_code=400, detail=f"Batch {batch_id} is currently running.")
            self.repository.delete_batch(batch_id)
        self._delete_mailbox_file(batch.source_file)

    def _delete_mailbox_file(self, source_file: str) -> None:
        # bulk_insert() batches use a synthetic "test:<timestamp>" source with no file on disk.
        if source_file.startswith("test:"):
            return
        path = self.mailbox_dir / source_file
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete mailbox file %s for a deleted batch.", source_file)

    def resume(self, batch_id: int) -> BatchStatus:
        with self.state.batch_lock:
            batch = self.get(batch_id)
            if batch.status == "completed":
                raise HTTPException(status_code=400, detail=f"Batch {batch_id} is already completed.")
            self._ensure_idle()
            self.state.active_batch_id = batch_id
        return self.get(batch_id)

    def pending_preview(self, batch_id: int) -> MailboxFilePreview:
        """Read-only preview of a batch's still-pending emails' timestamps, for resuming with a range."""
        self.get(batch_id)  # raises 404 when the batch does not exist
        emails = self.repository.pending_emails(batch_id)
        return MailboxFilePreview(received_at=[email.received_at for email in emails])

    def stop(self, batch_id: int) -> BatchStatus:
        with self.state.batch_lock:
            if self.state.active_batch_id != batch_id:
                self.get(batch_id)  # raises 404 when the batch does not exist
                raise HTTPException(status_code=400, detail=f"Batch {batch_id} is not currently running.")
            self.state.stop_batch_id = batch_id
        return self.get(batch_id)

    def run(
        self,
        batch_id: int,
        received_after: datetime | None = None,
        received_before: datetime | None = None,
    ) -> None:
        """Process pending emails in range; call it after start or resume claimed the slot."""
        logger.info("Batch %s: starting.", batch_id)
        stopped = False
        skipped = 0
        try:
            for email in self.repository.pending_emails(batch_id):
                if self.state.stop_batch_id == batch_id:
                    stopped = True
                    break
                if not self._in_range(email.received_at, received_after, received_before):
                    skipped += 1
                    continue
                response = self._triage(email)
                self.repository.save_result(email.id, response)
                logger.info("Batch %s: email %s -> %s.", batch_id, email.id, response.status)
            if stopped:
                logger.info("Batch %s: stopped.", batch_id)
            elif skipped:
                logger.info("Batch %s: finished this pass, %s emails outside the range remain pending.",
                             batch_id, skipped)
            else:
                self.repository.mark_completed(batch_id)
                logger.info("Batch %s: completed.", batch_id)
        finally:
            # Released even on a crash, leaving the batch running but inactive, so it can be resumed.
            if self.state.active_batch_id == batch_id:
                self.state.active_batch_id = None
            if self.state.stop_batch_id == batch_id:
                self.state.stop_batch_id = None

    def get(self, batch_id: int) -> BatchStatus:
        batch = self.repository.get_batch(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found.")
        return self._with_activity(batch)

    def list_batches(self, limit: int | None = None, offset: int = 0) -> list[BatchStatus]:
        return [
            self._with_activity(batch)
            for batch in self.repository.list_batches(limit, offset)
        ]

    def emails(
        self, batch_id: int | None = None, limit: int | None = None, offset: int = 0
    ) -> list[ReviewableEmail]:
        return self.repository.list_emails(batch_id, limit, offset)

    def review(self, email_id: int, action: ReviewActionType, edited_reply: str | None) -> ReviewAction:
        email = self.repository.get_email(email_id)
        if email is None:
            raise HTTPException(status_code=404, detail=f"No email '{email_id}'.")
        return self.repository.save_review_action(email_id, action, edited_reply)

    def upload_mailbox_file(self, original_name: str, content: bytes, display_name: str | None = None) -> MailboxFileUpload:
        """Stores an uploaded mailbox file under MAILBOX_DIR; the client starts a batch from the returned name.
        Recorded as pending under display_name (or the stored name) until a batch starts from it."""
        suffix = Path(original_name or "").suffix.lower()
        if suffix not in SUPPORTED_MAILBOX_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_MAILBOX_EXTENSIONS))
            raise HTTPException(status_code=400, detail=f"Unsupported file type {suffix!r}; supported: {supported}.")
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > MAX_MAILBOX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Uploaded file exceeds the {MAX_MAILBOX_UPLOAD_BYTES} byte limit.",
            )
        self.mailbox_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"upload-{uuid.uuid4().hex}{suffix}"
        (self.mailbox_dir / stored_name).write_bytes(content)
        self.repository.save_pending_mailbox_file(stored_name, display_name or stored_name)
        return MailboxFileUpload(file=stored_name)

    def pending_mailbox_files(self) -> list[PendingMailboxFile]:
        return self.repository.list_pending_mailbox_files()

    def discard_pending_mailbox_file(self, file: str) -> None:
        self.repository.delete_pending_mailbox_file(file)

    def preview_mailbox_file(self, file_name: str) -> MailboxFilePreview:
        """Reads a mailbox file's email timestamps without creating a batch."""
        path = self._resolve(file_name)
        try:
            emails = get_email_loader(path).load(path)
        except EmailLoadError as error:
            raise HTTPException(status_code=400, detail=str(error))
        return MailboxFilePreview(received_at=[email.received_at for email in emails])

    def _in_range(
        self,
        received_at: datetime | None,
        received_after: datetime | None,
        received_before: datetime | None,
    ) -> bool:
        if received_after is None and received_before is None:
            return True
        if received_at is None:
            return False
        if received_after is not None and received_at < received_after:
            return False
        if received_before is not None and received_at > received_before:
            return False
        return True

    def _with_activity(self, batch: BatchStatus) -> BatchStatus:
        return batch.model_copy(update={"active": self.state.active_batch_id == batch.id})

    def _ensure_idle(self) -> None:
        if self.state.active_batch_id is not None:
            raise HTTPException(status_code=400, detail="A batch is already running.")

    def _synthetic_emails(self) -> list[LoadedEmail]:
        now = datetime.now(timezone.utc)
        return [
            LoadedEmail(
                sender=f"test.customer{n}@example.com",
                subject=f"Test email {n}",
                body_clean=f"This is synthetic test email {n} for bulk-insert testing.",
                received_at=now - timedelta(minutes=n - 1),
            )
            for n in range(1, BULK_INSERT_SIZE + 1)
        ]

    def _resolve(self, file_name: str) -> Path:
        # A bare name inside the mailbox folder keeps a client from pointing at any other server file.
        if file_name in ("", ".", "..") or Path(file_name).name != file_name:
            raise HTTPException(status_code=400, detail="File must be a bare file name in the mailbox folder.")
        path = self.mailbox_dir / file_name
        if path.is_symlink():
            raise HTTPException(status_code=400, detail=f"Mailbox file not found: {file_name}")
        if not path.is_file():
            raise HTTPException(status_code=400, detail=f"Mailbox file not found: {file_name}")
        return path

    def _triage(self, email: StoredEmail) -> TriageResponse:
        try:
            request = TriageRequest(sender=email.sender or None, subject=email.subject, body=email.body_clean)
        except ValidationError as error:
            first = error.errors()[0]
            field = ".".join(str(part) for part in first["loc"])
            return TriageResponse(
                status="needs_review", model=self.state.active_model, attempts=0, latency_sec=0.0,
                failure_reason=f"The email was not sent to the model ({field}: {first['msg']}).",
            )
        return self.triage.triage(request)
