from fastapi import HTTPException

from app.clients.base import ILLMClient
from app.services.model_loading import unload_others
from app.state import AppState


class AssistantService:
    """Coordinates business rules using the injected LLM Client and State."""

    def __init__(self, client: ILLMClient, state: AppState):
        self.client = client
        self.state = state

    def process_chat(self, prompt: str) -> dict:
        try:
            unload_others(self.client, self.state.active_model)
            return self.client.generate(self.state.active_model, prompt, self.state.active_temperature)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM Generation failed: {str(e)}")

    def list_available_models(self) -> list[str]:
        try:
            return self.client.list_available_models()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list installed models: {str(e)}")

    def active_settings(self) -> tuple[str, float]:
        return self.state.active_model, self.state.active_temperature

    def switch_active_model(self, new_model: str) -> str:
        if new_model not in self.list_available_models():
            raise HTTPException(status_code=400, detail=f"Model {new_model} is not installed in Ollama.")
        try:
            unload_others(self.client, new_model)
            self.client.load_model(new_model)
            self.state.active_model = new_model
            return new_model
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to switch models: {str(e)}")

    def update_temperature(self, temp: float) -> float:
        if not (0.0 <= temp <= 2.0):
            raise HTTPException(status_code=400, detail="Temperature must be between 0.0 and 2.0")
        self.state.active_temperature = temp
        return temp
