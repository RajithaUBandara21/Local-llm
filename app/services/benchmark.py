from app.clients.base import ILLMClient
from app.config import MODELS
from app.services.benchmark_runner import run_benchmark_for_model
from app.services.model_loading import unload_others
from app.state import AppState


class BenchmarkService:
    """Coordinates benchmark execution."""

    def __init__(self, state: AppState, client: ILLMClient):
        self.state = state
        self.client = client

    def run_pipeline(self):
        self.state.benchmark_running = True
        try:
            for model in MODELS:
                unload_others(self.client, model)
                run_benchmark_for_model(model)
                self._release(model)
        finally:
            self.state.benchmark_running = False

    def _release(self, model: str) -> None:
        # Best-effort: the next model's unload_others pass clears a leftover anyway.
        print(f"\n[RESOURCE OPTIMIZATION] Unloading {model} from VRAM...")
        try:
            self.client.unload_model(model)
            print(f"[RESOURCE OPTIMIZATION] {model} successfully unloaded.\n")
        except Exception as e:
            print(f"[RESOURCE OPTIMIZATION] Failed to unload {model}: {e}\n")
