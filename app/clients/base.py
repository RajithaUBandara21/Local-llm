from abc import ABC, abstractmethod


class ILLMClient(ABC):
    """Abstract interface for LLM interactions."""

    @abstractmethod
    def generate(self, model: str, prompt: str, temperature: float) -> dict: pass

    @abstractmethod
    def load_model(self, model: str) -> None: pass

    @abstractmethod
    def unload_model(self, model: str) -> None: pass
