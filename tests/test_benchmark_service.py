import pytest

from app.config import MODELS
from app.services import benchmark
from app.services.benchmark import BenchmarkService
from app.state import AppState
from tests.fakes import FakeClient


def track_runs(monkeypatch, client, state=None):
    def run(model):
        client.calls.append(("run", model, state.benchmark_running if state else None))

    monkeypatch.setattr(benchmark, "run_benchmark_for_model", run)


def test_pipeline_runs_every_model_and_flags_running_meanwhile(monkeypatch):
    state = AppState()
    client = FakeClient()
    track_runs(monkeypatch, client, state)

    BenchmarkService(state, client).run_pipeline()

    runs = [call for call in client.calls if call[0] == "run"]
    assert runs == [("run", model, True) for model in MODELS]
    assert state.benchmark_running is False


def test_each_model_is_isolated_before_its_run_and_released_after(monkeypatch):
    client = FakeClient(loaded=["stray:latest"])
    track_runs(monkeypatch, client)

    BenchmarkService(AppState(), client).run_pipeline()

    expected = []
    for model in MODELS:
        expected += [
            ("list_loaded_models",),
            ("unload_model", "stray:latest"),
            ("run", model, None),
            ("unload_model", model),
        ]
    assert client.calls == expected


def test_a_failing_release_does_not_stop_the_pipeline(monkeypatch):
    class ReleaseFails(FakeClient):
        def unload_model(self, model):
            self._record("unload_model", model)
            if model in MODELS:
                raise RuntimeError("unload failed")

    client = ReleaseFails()
    track_runs(monkeypatch, client)
    state = AppState()

    BenchmarkService(state, client).run_pipeline()

    runs = [call[1] for call in client.calls if call[0] == "run"]
    assert runs == MODELS
    assert state.benchmark_running is False


def test_a_failing_isolation_stops_the_pipeline_before_any_run(monkeypatch):
    client = FakeClient(fail_on="list_loaded_models")
    track_runs(monkeypatch, client)
    state = AppState()
    service = BenchmarkService(state, client)

    with pytest.raises(RuntimeError, match="list_loaded_models failed"):
        service.run_pipeline()

    assert [call for call in client.calls if call[0] == "run"] == []
    assert state.benchmark_running is False


def test_running_flag_is_reset_when_a_model_run_raises(monkeypatch):
    state = AppState()

    def explode(model):
        raise RuntimeError("ollama went away")

    monkeypatch.setattr(benchmark, "run_benchmark_for_model", explode)
    service = BenchmarkService(state, FakeClient())

    with pytest.raises(RuntimeError):
        service.run_pipeline()

    assert state.benchmark_running is False
