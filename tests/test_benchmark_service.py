import pytest

from app.config import MODELS
from app.services import benchmark
from app.services.benchmark import BenchmarkService
from app.state import AppState


def test_pipeline_runs_every_model_and_flags_running_meanwhile(monkeypatch):
    state = AppState()
    seen = []
    monkeypatch.setattr(
        benchmark, "run_benchmark_for_model", lambda model: seen.append((model, state.benchmark_running))
    )

    BenchmarkService(state).run_pipeline()

    assert seen == [(model, True) for model in MODELS]
    assert state.benchmark_running is False


def test_running_flag_is_reset_when_a_model_run_raises(monkeypatch):
    state = AppState()

    def explode(model):
        raise RuntimeError("ollama went away")

    monkeypatch.setattr(benchmark, "run_benchmark_for_model", explode)

    with pytest.raises(RuntimeError):
        BenchmarkService(state).run_pipeline()

    assert state.benchmark_running is False
