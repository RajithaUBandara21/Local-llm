from app.config import MODELS
from app.services.benchmark_runner import run_benchmark_for_model
from app.state import AppState


class BenchmarkService:
    """Coordinates benchmark execution."""

    def __init__(self, state: AppState):
        self.state = state

    def run_pipeline(self):
        self.state.benchmark_running = True
        try:
            for model in MODELS:
                run_benchmark_for_model(model)
        finally:
            self.state.benchmark_running = False
