from dataclasses import dataclass

from fastapi import HTTPException

from app.clients.base import ILLMClient
from app.config import MAX_RUNS_PER_PROMPT, MODELS, RUNS_PER_PROMPT, TEMPERATURES
from app.schemas import BenchmarkRequest
from app.services.benchmark_runner import create_results_file, run_benchmark_for_model
from app.services.model_loading import unload_others
from app.state import AppState


@dataclass
class BenchmarkPlan:
    """What one benchmark run will do: each model once, with its temperatures."""
    runs_per_prompt: int
    jobs: list[tuple[str, list[float]]]


class BenchmarkService:
    """Coordinates benchmark execution."""

    def __init__(self, state: AppState, client: ILLMClient):
        self.state = state
        self.client = client

    def build_plan(self, request: BenchmarkRequest | None) -> BenchmarkPlan:
        """Turn a start request into a plan; no request means every model at every temperature."""
        request = request or BenchmarkRequest()
        runs = RUNS_PER_PROMPT if request.runs_per_prompt is None else request.runs_per_prompt
        if not 1 <= runs <= MAX_RUNS_PER_PROMPT:
            raise HTTPException(
                status_code=400,
                detail=f"runs_per_prompt must be between 1 and {MAX_RUNS_PER_PROMPT}",
            )

        if request.configs is None:
            return BenchmarkPlan(runs, [(model, list(TEMPERATURES)) for model in MODELS])
        if not request.configs:
            raise HTTPException(status_code=400, detail="configs must not be empty")

        # Grouping by model loads each model once, however its settings are ordered.
        temperatures_by_model: dict[str, list[float]] = {}
        for setting in request.configs:
            if setting.model not in MODELS:
                raise HTTPException(status_code=400, detail=f"Model {setting.model} not configured.")
            if not 0.0 <= setting.temperature <= 2.0:
                raise HTTPException(status_code=400, detail="Temperature must be between 0.0 and 2.0")
            temperatures = temperatures_by_model.setdefault(setting.model, [])
            if setting.temperature in temperatures:
                raise HTTPException(
                    status_code=400,
                    detail=f"Duplicate setting: {setting.model} at temperature {setting.temperature}",
                )
            temperatures.append(setting.temperature)
        return BenchmarkPlan(runs, list(temperatures_by_model.items()))

    def run_pipeline(self, plan: BenchmarkPlan):
        self.state.benchmark_running = True
        try:
            results_file = create_results_file()
            for model, temperatures in plan.jobs:
                unload_others(self.client, model)
                run_benchmark_for_model(model, results_file, temperatures, plan.runs_per_prompt)
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
