from app.clients.base import ILLMClient


def _base_name(name: str) -> str:
    # Ollama reports "llama3.2:latest" for a model configured as "llama3.2".
    return name.removesuffix(":latest")


def unload_others(client: ILLMClient, model: str) -> None:
    """Unload every loaded model except `model` so measurements belong to one model."""
    wanted = _base_name(model)
    for loaded in client.list_loaded_models():
        if _base_name(loaded) != wanted:
            client.unload_model(loaded)
