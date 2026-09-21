from pydantic import BaseModel, Field


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
