from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.dependencies import get_benchmark_service, get_metrics_repository
from app.repositories.base import IMetricsRepository
from app.services.benchmark import BenchmarkService
from app.state import AppState, get_app_state

router = APIRouter()


@router.post("/api/benchmark/start")
def start_benchmark_endpoint(
    background_tasks: BackgroundTasks,
    state: AppState = Depends(get_app_state),
    service: BenchmarkService = Depends(get_benchmark_service)
):
    if state.benchmark_running:
        raise HTTPException(status_code=400, detail="A benchmark is already running.")

    background_tasks.add_task(service.run_pipeline)
    return {"status": "Benchmark initiated in the background."}


@router.get("/api/benchmark/status")
def get_benchmark_status_endpoint(state: AppState = Depends(get_app_state)):
    return {"benchmark_running": state.benchmark_running}


@router.get("/api/benchmark/metrics")
def get_dashboard_metrics_endpoint(
    repo: IMetricsRepository = Depends(get_metrics_repository)
):
    try:
        return repo.get_latest_metrics()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
