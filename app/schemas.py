from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


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
