from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.config import TRIAGE_MAX_BODY_CHARS


class UniversalResponse(BaseModel):
    """A universal schema enforcing Chain-of-Thought reasoning for all prompts."""
    reasoning: str = Field(description="Step-by-step logical deduction or thought process.")
    final_answer: str = Field(description="The exact answer, code, or summary requested.")
    confidence_score: float = Field(description="A score between 0.0 and 1.0 indicating confidence.")


class ChatRequest(BaseModel):
    prompt: str


class ModelChangeRequest(BaseModel):
    model_name: str


class TemperatureRequest(BaseModel):
    temperature: float


class BenchmarkSetting(BaseModel):
    model: str
    temperature: float


class BenchmarkRequest(BaseModel):
    configs: list[BenchmarkSetting] | None = None
    runs_per_prompt: int | None = None


class LoadedEmail(BaseModel):
    """One cleaned email from a mailbox file, before it is stored or triaged."""
    sender: str
    subject: str
    body_clean: str
    received_at: datetime | None
    mailbox: str | None

    @field_validator("received_at")
    @classmethod
    def _to_utc(cls, value: datetime | None) -> datetime | None:
        # Source files mix offsets and naive times; one zone keeps later comparisons safe.
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


Category = Literal["refund", "delivery", "billing", "complaint", "inquiry", "spam", "other"]
Priority = Literal["urgent", "high", "normal", "low"]
Flag = Literal["stale_context", "out_of_policy"]
TriageStatus = Literal["ok", "needs_review", "failed"]
ReviewActionType = Literal["approve", "edit", "reject"]

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TriageResult(BaseModel):
    """What the model must return for one email; the pipeline, not the model, decides manual review."""
    category: Category = Field(description="The customer's main ask decides the category.")
    priority: Priority = Field(description="Urgency from money or legal exposure, time-sensitivity, and repeat contact.")
    summary: NonBlankText = Field(description="One or two sentences describing the email.")
    suggested_reply: str | None = Field(description="Draft reply for a person to review, or null when out_of_policy is flagged.")
    confidence: float = Field(ge=0.0, le=1.0, description="A score between 0.0 and 1.0.")
    flags: list[Flag] = Field(default_factory=list, description="Empty unless stale_context or out_of_policy applies.")
    flag_reason: str | None = Field(default=None, description="Required when flags is not empty, otherwise null.")

    @model_validator(mode="after")
    def _check_flag_rules(self) -> "TriageResult":
        if self.flags and not (self.flag_reason or "").strip():
            raise ValueError("flag_reason is required when flags is not empty")
        if not self.flags and self.flag_reason is not None:
            raise ValueError("flag_reason must be null when flags is empty")
        has_reply = bool((self.suggested_reply or "").strip())
        if "out_of_policy" in self.flags and self.suggested_reply is not None:
            raise ValueError("suggested_reply must be null when out_of_policy is flagged")
        if "out_of_policy" not in self.flags and not has_reply:
            raise ValueError("suggested_reply is required unless out_of_policy is flagged")
        return self


class TriageRequest(BaseModel):
    """One already cleaned email; the loaders produce this shape."""
    sender: str | None = Field(default=None, max_length=320)
    subject: str = Field(default="", max_length=500)
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TRIAGE_MAX_BODY_CHARS)]


class TriageResponse(BaseModel):
    """`needs_review` and `failed` both send the email to a person; only the pipeline sets them."""
    status: TriageStatus
    model: str
    attempts: int
    latency_sec: float
    result: TriageResult | None = None
    failure_reason: str | None = None


class StoredEmail(LoadedEmail):
    """An email row in a batch; ids grow in file order."""
    id: int


class BatchRequest(BaseModel):
    """Names a file inside the server's mailbox folder; never a path."""
    file: NonBlankText


class BatchStatus(BaseModel):
    """`processed` is the number of stored results; `active` means a worker in this process is on it."""
    id: int
    source_file: str
    status: Literal["running", "completed"]
    active: bool = False
    total: int
    processed: int
    ok: int
    needs_review: int
    failed: int
    created_at: datetime
    finished_at: datetime | None = None


class Agent(BaseModel):
    id: NonBlankText
    name: NonBlankText


class AgentRenameRequest(BaseModel):
    name: NonBlankText


class MailboxCreateRequest(BaseModel):
    name: NonBlankText


class Seed(BaseModel):
    """Agents and which of them may read each mailbox, as loaded from the seed file."""
    agents: list[Agent]
    assignments: dict[str, list[str]]


class ReviewActionRequest(BaseModel):
    """An agent's decision on one email's suggested reply."""
    action: ReviewActionType
    edited_reply: str | None = None

    @model_validator(mode="after")
    def _check_edited_reply(self) -> "ReviewActionRequest":
        has_text = bool((self.edited_reply or "").strip())
        if self.action == "edit" and not has_text:
            raise ValueError("edited_reply is required when action is edit")
        if self.action != "edit" and self.edited_reply is not None:
            raise ValueError("edited_reply must be null unless action is edit")
        return self


class ReviewAction(BaseModel):
    """A stored review decision; every action is kept, the latest is shown on MailboxEmail."""
    id: int
    email_id: int
    agent_id: str
    action: ReviewActionType
    edited_reply: str | None = None
    created_at: datetime


class MailboxEmail(StoredEmail):
    """An email as an agent sees it: its batch, the stored triage outcome, and the latest review action, if any."""
    batch_id: int
    triage: TriageResponse | None = None
    review: ReviewAction | None = None
