from abc import ABC, abstractmethod


class LLMTimeoutError(Exception):
    """The model did not answer within the time allowed."""


class ILLMClient(ABC):
    """Abstract interface for LLM interactions."""

    @abstractmethod
    def generate(
        self, model: str, prompt: str, temperature: float,
        schema: dict | None = None, timeout: float | None = None
    ) -> dict:
        """Return the model reply; `schema` constrains its JSON, `timeout` raises LLMTimeoutError."""

    @abstractmethod
    def load_model(self, model: str) -> None: pass

    @abstractmethod
    def unload_model(self, model: str) -> None: pass

    @abstractmethod
    def list_loaded_models(self) -> list[str]: pass

    @abstractmethod
    def list_available_models(self) -> list[str]:
        """Every model Ollama has installed locally, regardless of load state."""
