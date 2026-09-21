from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from app.loaders.base import EmailLoadError
from app.loaders.factory import get_email_loader
from app.repositories.base import IBatchRepository
from app.schemas import BatchStatus, StoredEmail, TriageRequest, TriageResponse
from app.services.triage import TriageService
from app.state import AppState


class BatchService:
    """Stores a mailbox file as a batch and triages its emails one at a time, resumably."""

    def __init__(
        self, repository: IBatchRepository, triage: TriageService, state: AppState, mailbox_dir: Path
    ):
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
