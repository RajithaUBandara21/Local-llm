import pytest
from fastapi import HTTPException

from app.config import MAX_RUNS_PER_PROMPT, MODELS, RUNS_PER_PROMPT, TEMPERATURES
from app.schemas import BenchmarkRequest, BenchmarkSetting
from app.services import benchmark
from app.services.benchmark import BenchmarkPlan, BenchmarkService
from app.state import AppState
from tests.fakes import FakeClient


def default_plan():
    return BenchmarkService(AppState(), FakeClient()).build_plan(None)


def track_runs(monkeypatch, client, state=None):
    def run(model, results_file, temperatures, runs_per_prompt):
        client.calls.append(("run", model, state.benchmark_running if state else None))

    monkeypatch.setattr(benchmark, "run_benchmark_for_model", run)


def test_pipeline_runs_every_model_and_flags_running_meanwhile(monkeypatch):
    state = AppState()
    client = FakeClient()
    track_runs(monkeypatch, client, state)

    BenchmarkService(state, client).run_pipeline(default_plan())

    runs = [call for call in client.calls if call[0] == "run"]
    assert runs == [("run", model, True) for model in MODELS]
    assert state.benchmark_running is False


def test_every_model_appends_to_one_shared_results_file(monkeypatch):
    files = []
    monkeypatch.setattr(benchmark, "create_results_file", lambda: "results/run.csv")
    monkeypatch.setattr(
        benchmark,
        "run_benchmark_for_model",
        lambda model, results_file, temperatures, runs_per_prompt: files.append(results_file),
    )

    BenchmarkService(AppState(), FakeClient()).run_pipeline(default_plan())

    assert files == ["results/run.csv"] * len(MODELS)


def test_each_job_runs_with_its_own_temperatures_and_the_plan_runs(monkeypatch):
    seen = []
    monkeypatch.setattr(
        benchmark,
        "run_benchmark_for_model",
        lambda model, results_file, temperatures, runs_per_prompt: seen.append(
            (model, temperatures, runs_per_prompt)
        ),
    )
    plan = BenchmarkPlan(2, [("llama3.2", [0.7]), ("phi-4-Q4", [0.0, 0.7])])

    BenchmarkService(AppState(), FakeClient()).run_pipeline(plan)

    assert seen == [("llama3.2", [0.7], 2), ("phi-4-Q4", [0.0, 0.7], 2)]


def test_each_model_is_isolated_before_its_run_and_released_after(monkeypatch):
    client = FakeClient(loaded=["stray:latest"])
    track_runs(monkeypatch, client)

    BenchmarkService(AppState(), client).run_pipeline(default_plan())

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

    BenchmarkService(state, client).run_pipeline(default_plan())

    runs = [call[1] for call in client.calls if call[0] == "run"]
    assert runs == MODELS
    assert state.benchmark_running is False


def test_a_failing_isolation_stops_the_pipeline_before_any_run(monkeypatch):
    client = FakeClient(fail_on="list_loaded_models")
    track_runs(monkeypatch, client)
    state = AppState()
    service = BenchmarkService(state, client)

    with pytest.raises(RuntimeError, match="list_loaded_models failed"):
        service.run_pipeline(default_plan())

    assert [call for call in client.calls if call[0] == "run"] == []
    assert state.benchmark_running is False


def test_running_flag_is_reset_when_a_model_run_raises(monkeypatch):
    state = AppState()

    def explode(model, results_file, temperatures, runs_per_prompt):
        raise RuntimeError("ollama went away")

    monkeypatch.setattr(benchmark, "run_benchmark_for_model", explode)
    service = BenchmarkService(state, FakeClient())

    with pytest.raises(RuntimeError):
        service.run_pipeline(default_plan())

    assert state.benchmark_running is False


def plan_for(request):
    return BenchmarkService(AppState(), FakeClient()).build_plan(request)


def setting(model, temperature):
    return BenchmarkSetting(model=model, temperature=temperature)


@pytest.mark.parametrize("request_body", [None, BenchmarkRequest()])
def test_no_settings_means_every_model_at_every_temperature(request_body):
    plan = plan_for(request_body)

    assert plan.runs_per_prompt == RUNS_PER_PROMPT
    assert plan.jobs == [(model, TEMPERATURES) for model in MODELS]


def test_settings_are_grouped_by_model_in_first_seen_order():
    plan = plan_for(
        BenchmarkRequest(
            runs_per_prompt=1,
            configs=[setting("phi-4-Q4", 0.0), setting("llama3.2", 0.7), setting("phi-4-Q4", 0.7)],
        )
    )

    assert plan.runs_per_prompt == 1
    assert plan.jobs == [("phi-4-Q4", [0.0, 0.7]), ("llama3.2", [0.7])]


def test_runs_per_prompt_can_be_set_without_settings():
    plan = plan_for(BenchmarkRequest(runs_per_prompt=2))

    assert plan.runs_per_prompt == 2
    assert [model for model, _ in plan.jobs] == MODELS


@pytest.mark.parametrize(
    "request_body, message",
    [
        (BenchmarkRequest(configs=[]), "configs must not be empty"),
        (BenchmarkRequest(configs=[setting("gpt-9", 0.0)]), "Model gpt-9 not configured."),
        (BenchmarkRequest(configs=[setting("llama3.2", 2.1)]), "Temperature must be between 0.0 and 2.0"),
        (BenchmarkRequest(configs=[setting("llama3.2", -0.1)]), "Temperature must be between 0.0 and 2.0"),
        (
            BenchmarkRequest(configs=[setting("llama3.2", 0.7), setting("llama3.2", 0.7)]),
            "Duplicate setting: llama3.2 at temperature 0.7",
        ),
        (BenchmarkRequest(runs_per_prompt=0), f"runs_per_prompt must be between 1 and {MAX_RUNS_PER_PROMPT}"),
        (
            BenchmarkRequest(runs_per_prompt=MAX_RUNS_PER_PROMPT + 1),
            f"runs_per_prompt must be between 1 and {MAX_RUNS_PER_PROMPT}",
        ),
    ],
)
def test_bad_requests_are_refused_with_a_400(request_body, message):
    with pytest.raises(HTTPException) as error:
        plan_for(request_body)

    assert error.value.status_code == 400
    assert error.value.detail == message
