import requests

from app.clients.base import ILLMClient, LLMTimeoutError


class OllamaClient(ILLMClient):
    """Handles direct HTTP communication with the Ollama API."""

    def __init__(self, base_url: str, ps_url: str):
        self.base_url = base_url
        self.ps_url = ps_url

    def generate(
        self, model: str, prompt: str, temperature: float,
        schema: dict | None = None, timeout: float | None = None
    ) -> dict:
        payload = {
            "model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": temperature}
        }
        if schema is not None:
            payload["format"] = schema
        try:
            response = requests.post(self.base_url, json=payload, timeout=timeout)
        except requests.Timeout as error:
            raise LLMTimeoutError(f"No reply from {model} within {timeout} s.") from error
        response.raise_for_status()
        return response.json()

    def load_model(self, model: str) -> None:
        requests.post(self.base_url, json={"model": model, "keep_alive": -1}).raise_for_status()

    def unload_model(self, model: str) -> None:
        requests.post(self.base_url, json={"model": model, "keep_alive": 0}).raise_for_status()

    def list_loaded_models(self) -> list[str]:
        response = requests.get(self.ps_url)
        response.raise_for_status()
        return [entry["name"] for entry in response.json()["models"]]
