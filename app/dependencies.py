from fastapi import Depends

from app.clients.base import ILLMClient
from app.clients.ollama import OllamaClient
from app.config import OLLAMA_GENERATE_URL, OLLAMA_PS_URL, RESULTS_DIR
from app.repositories.base import IMetricsRepository
from app.repositories.csv_metrics import CSVMetricsRepository
from app.services.assistant import AssistantService
from app.services.benchmark import BenchmarkService
from app.state import AppState, get_app_state


def get_llm_client() -> ILLMClient:
    return OllamaClient(OLLAMA_GENERATE_URL, OLLAMA_PS_URL)


def get_metrics_repository() -> IMetricsRepository:
    return CSVMetricsRepository(RESULTS_DIR)


def get_assistant_service(
    client: ILLMClient = Depends(get_llm_client),
    state: AppState = Depends(get_app_state)
) -> AssistantService:
    return AssistantService(client, state)


def get_benchmark_service(
    client: ILLMClient = Depends(get_llm_client),
    state: AppState = Depends(get_app_state)
) -> BenchmarkService:
    return BenchmarkService(state, client)
