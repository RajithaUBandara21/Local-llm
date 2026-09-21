from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.dependencies import get_benchmark_service, get_metrics_repository
from app.repositories.base import IMetricsRepository
from app.schemas import BenchmarkRequest
from app.services.benchmark import BenchmarkService
from app.state import AppState, get_app_state

router = APIRouter()


@router.post("/api/benchmark/start")
def start_benchmark_endpoint(
    background_tasks: BackgroundTasks,
    state: AppState = Depends(get_app_state),
    service: BenchmarkService = Depends(get_benchmark_service),
    request: BenchmarkRequest | None = None
):
    if state.benchmark_running:
        raise HTTPException(status_code=400, detail="A benchmark is already running.")
    if state.active_batch_id is not None:
        # Starting a benchmark would unload the model the batch is using.
        raise HTTPException(status_code=400, detail="A triage batch is running; try again when it finishes.")

    # Built here so a bad request gets its 400 now instead of failing in the background.
    plan = service.build_plan(request)
    background_tasks.add_task(service.run_pipeline, plan)
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
