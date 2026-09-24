from pathlib import Path

from fastapi import Depends

from app.clients.base import ILLMClient
from app.clients.ollama import OllamaClient
from app.config import DATABASE_PATH, MAILBOX_DIR, OLLAMA_GENERATE_URL, OLLAMA_PS_URL, OLLAMA_TAGS_URL, RESULTS_DIR
from app.repositories.base import IBatchRepository, IGmailRepository, IMetricsRepository
from app.repositories.csv_metrics import CSVMetricsRepository
from app.repositories.sqlite_batches import SQLiteBatchRepository
from app.repositories.sqlite_gmail import SQLiteGmailRepository
from app.services.assistant import AssistantService
from app.services.batch import BatchService
from app.services.benchmark import BenchmarkService
from app.services.gmail_oauth import GmailOAuthService
from app.services.triage import TriageService
from app.state import AppState, get_app_state


def get_llm_client() -> ILLMClient:
    return OllamaClient(OLLAMA_GENERATE_URL, OLLAMA_PS_URL, OLLAMA_TAGS_URL)


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


def get_triage_service(
    client: ILLMClient = Depends(get_llm_client),
    state: AppState = Depends(get_app_state)
) -> TriageService:
    return TriageService(client, state)


def get_batch_repository() -> IBatchRepository:
    return SQLiteBatchRepository(DATABASE_PATH)


def get_gmail_repository() -> IGmailRepository:
    return SQLiteGmailRepository(DATABASE_PATH)


def get_batch_service(
    repository: IBatchRepository = Depends(get_batch_repository),
    client: ILLMClient = Depends(get_llm_client),
    state: AppState = Depends(get_app_state),
) -> BatchService:
    return BatchService(repository, TriageService(client, state), state, Path(MAILBOX_DIR))


def get_gmail_oauth_service(
    gmail: IGmailRepository = Depends(get_gmail_repository),
    state: AppState = Depends(get_app_state)
) -> GmailOAuthService:
    return GmailOAuthService(gmail, state)
