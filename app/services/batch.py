from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from app.loaders.base import EmailLoadError
from app.loaders.factory import get_email_loader
from app.repositories.base import IAccessRepository, IBatchRepository
from app.schemas import BatchStatus, LoadedEmail, StoredEmail, TriageRequest, TriageResponse
from app.services.triage import TriageService
from app.state import AppState

# Matches the frontend mock's batch size (web/lib/constants.ts MOCK_BATCH_SIZE),
# so the real bulk-insert produces the same shape the client used to fake.
BULK_INSERT_SIZE = 10


class BatchService:
    """Stores a mailbox file as a batch and triages its emails one at a time, resumably."""

    def __init__(
        self, repository: IBatchRepository, triage: TriageService, state: AppState, mailbox_dir: Path,
        access: IAccessRepository,
    ):
        self.repository = repository
        self.triage = triage
        self.state = state
        self.mailbox_dir = mailbox_dir
        self.access = access

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

    def bulk_insert(self, mailbox: str) -> BatchStatus:
        with self.state.batch_lock:
            self._ensure_idle()
            if mailbox not in self._known_mailboxes():
                raise HTTPException(status_code=400, detail=f"Unknown mailbox: {mailbox}")
            source_file = f"test:{mailbox}:{datetime.now(timezone.utc).isoformat()}"
            batch_id = self.repository.create_batch(source_file, self._synthetic_emails(mailbox))
            self.state.active_batch_id = batch_id
        return self.get(batch_id)

    def delete(self, batch_id: int) -> None:
        self.get(batch_id)  # raises 404 when the batch does not exist
        with self.state.batch_lock:
            if self.state.active_batch_id == batch_id:
                raise HTTPException(status_code=400, detail=f"Batch {batch_id} is currently running.")
            self.repository.delete_batch(batch_id)

    def resume(self, batch_id: int) -> BatchStatus:
        with self.state.batch_lock:
            batch = self.get(batch_id)
            if batch.status == "completed":
                raise HTTPException(status_code=400, detail=f"Batch {batch_id} is already completed.")
            self._ensure_idle()
            self.state.active_batch_id = batch_id
        return self.get(batch_id)

    def run(self, batch_id: int) -> None:
        """Process the emails that have no result yet; call it after start or resume claimed the slot."""
        try:
            for email in self.repository.pending_emails(batch_id):
                self.repository.save_result(email.id, self._triage(email))
            self.repository.mark_completed(batch_id)
        finally:
            # Released even on a crash, leaving the batch running but inactive, so it can be resumed.
            if self.state.active_batch_id == batch_id:
                self.state.active_batch_id = None

    def get(self, batch_id: int) -> BatchStatus:
        batch = self.repository.get_batch(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found.")
        return self._with_activity(batch)

    def list_batches(self) -> list[BatchStatus]:
        return [self._with_activity(batch) for batch in self.repository.list_batches()]

    def _with_activity(self, batch: BatchStatus) -> BatchStatus:
        return batch.model_copy(update={"active": self.state.active_batch_id == batch.id})

    def _ensure_idle(self) -> None:
        if self.state.active_batch_id is not None:
            raise HTTPException(status_code=400, detail="A batch is already running.")
        if self.state.benchmark_running:
            raise HTTPException(status_code=400, detail="A benchmark is running; try again when it finishes.")

    def _known_mailboxes(self) -> set[str]:
        mailboxes: set[str] = set()
        for agent in self.access.list_agents():
            mailboxes.update(self.access.mailboxes_for(agent.id))
        return mailboxes

    def _synthetic_emails(self, mailbox: str) -> list[LoadedEmail]:
        now = datetime.now(timezone.utc)
        return [
            LoadedEmail(
                sender=f"test.customer{n}@example.com",
                subject=f"Test email {n}",
                body_clean=f"This is synthetic test email {n} for bulk-insert testing.",
                received_at=now - timedelta(minutes=n - 1),
                mailbox=mailbox,
            )
            for n in range(1, BULK_INSERT_SIZE + 1)
        ]

    def _resolve(self, file_name: str) -> Path:
        # A bare name inside the mailbox folder keeps a client from pointing at any other server file.
        if file_name in ("", ".", "..") or Path(file_name).name != file_name:
            raise HTTPException(status_code=400, detail="File must be a bare file name in the mailbox folder.")
        path = self.mailbox_dir / file_name
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
