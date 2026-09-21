import pytest
from fastapi import BackgroundTasks, HTTPException

from app.repositories.base import IMetricsRepository
from app.routes.benchmark import (
    get_benchmark_status_endpoint,
    get_dashboard_metrics_endpoint,
    start_benchmark_endpoint,
)
from app.routes.health import health_check
from app.services.benchmark import BenchmarkService
from app.state import AppState


class FakeRepository(IMetricsRepository):
    def __init__(self, error=None):
        self.error = error

    def get_latest_metrics(self):
        if self.error:
            raise self.error
        return {"latest_benchmark_file": "run.csv", "total_runs": 0, "data": []}


def test_health_reports_the_service():
    assert health_check() == {"status": "healthy", "service": "Local AI Assistant API"}


def test_start_schedules_the_pipeline_in_the_background():
    state = AppState()
    service = BenchmarkService(state)
    tasks = BackgroundTasks()

    result = start_benchmark_endpoint(tasks, state, service)

    assert result == {"status": "Benchmark initiated in the background."}
    assert [task.func for task in tasks.tasks] == [service.run_pipeline]


def test_start_is_refused_while_a_benchmark_is_running():
    state = AppState()
    state.benchmark_running = True
    tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as error:
        start_benchmark_endpoint(tasks, state, BenchmarkService(state))

    assert error.value.status_code == 400
    assert error.value.detail == "A benchmark is already running."
    assert tasks.tasks == []


@pytest.mark.parametrize("running", [False, True])
def test_status_reflects_the_running_flag(running):
    state = AppState()
    state.benchmark_running = running

    assert get_benchmark_status_endpoint(state) == {"benchmark_running": running}


def test_metrics_returns_the_repository_result():
    assert get_dashboard_metrics_endpoint(FakeRepository())["latest_benchmark_file"] == "run.csv"


def test_missing_results_map_to_404():
    repo = FakeRepository(FileNotFoundError("No benchmark CSV files found."))

    with pytest.raises(HTTPException) as error:
        get_dashboard_metrics_endpoint(repo)

    assert error.value.status_code == 404
    assert error.value.detail == "No benchmark CSV files found."
