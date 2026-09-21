import time

from fastapi import HTTPException

from app.clients.base import ILLMClient, LLMTimeoutError
from app.config import TRIAGE_MAX_ATTEMPTS, TRIAGE_TIMEOUT_SEC
from app.prompts import build_triage_prompt, build_triage_retry_prompt
from app.schemas import TriageRequest, TriageResponse, TriageResult, TriageStatus
from app.services.model_loading import unload_others
from app.services.output_validator import OutputValidator
from app.state import AppState


class TriageService:
    """Triages one email with the active model; every failure becomes a status, not an exception."""

    def __init__(self, client: ILLMClient, state: AppState):
        self.client = client
        self.state = state

    def triage(self, email: TriageRequest) -> TriageResponse:
        if self.state.benchmark_running:
            # Loading the triage model would unload the one the benchmark is measuring.
            raise HTTPException(status_code=400, detail="A benchmark is running; try again when it finishes.")

        model = self.state.active_model
        try:
            unload_others(self.client, model)
            # Loaded before the timed calls so a cold start is not charged to the timeout.
            self.client.load_model(model)
        except Exception as error:
            return TriageResponse(
                status="failed", model=model, attempts=0, latency_sec=0.0,
                failure_reason=f"Could not load the model: {error}",
            )
        return self._run_attempts(model, email)

    def _run_attempts(self, model: str, email: TriageRequest) -> TriageResponse:
        prompt = build_triage_prompt(email.sender, email.subject, email.body)
        schema = TriageResult.model_json_schema()
        attempt_prompt = prompt
        started = time.perf_counter()
        error_text = ""

        def respond(status: TriageStatus, attempts: int, **fields) -> TriageResponse:
            return TriageResponse(
                status=status, model=model, attempts=attempts,
                latency_sec=round(time.perf_counter() - started, 4), **fields,
            )

        for attempt in range(1, TRIAGE_MAX_ATTEMPTS + 1):
            try:
                reply = self.client.generate(
                    model, attempt_prompt, self.state.active_temperature,
                    schema=schema, timeout=TRIAGE_TIMEOUT_SEC,
                )
            except LLMTimeoutError:
                return respond("failed", attempt, failure_reason=f"The model did not answer within {TRIAGE_TIMEOUT_SEC} s.")
            except Exception as error:
                return respond("failed", attempt, failure_reason=f"The model call failed: {error}")

            is_valid, data, error_text = OutputValidator.validate_json(reply.get("response", ""), TriageResult)
            if is_valid:
                return respond("ok", attempt, result=data)
            attempt_prompt = build_triage_retry_prompt(prompt, error_text)

        return respond(
            "needs_review", TRIAGE_MAX_ATTEMPTS,
            failure_reason=f"Invalid model output after {TRIAGE_MAX_ATTEMPTS} attempts: {error_text}",
        )
