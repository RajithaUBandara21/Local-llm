import json

import pytest

from app.clients.base import LLMTimeoutError
from app.config import MODELS, TRIAGE_CONFIDENCE_THRESHOLD, TRIAGE_MAX_ATTEMPTS, TRIAGE_TIMEOUT_SEC
from app.schemas import TriageRequest, TriageResult
from app.services.triage import TriageService
from app.state import AppState
from tests.fakes import FakeClient

EMAIL = TriageRequest(sender="priya@example.com", subject="Where is my parcel", body="Tracking says in transit.")
VALID_REPLY = json.dumps({
    "category": "delivery",
    "priority": "normal",
    "summary": "Customer asks where the parcel is.",
    "suggested_reply": "Thanks for writing, we are checking the tracking.",
    "confidence": 0.9,
    "flags": [],
    "flag_reason": None,
})
INVALID_REPLY = json.dumps({"category": "delivery", "priority": "asap"})
LOW_CONFIDENCE_REPLY = json.dumps({**json.loads(VALID_REPLY), "confidence": 0.4})


def make_service(client):
    state = AppState()
    return TriageService(client, state), client, state


def generate_calls(client):
    return [call for call in client.calls if call[0] == "generate"]


def test_a_valid_reply_on_the_first_attempt_is_ok():
    service, client, state = make_service(FakeClient(replies=[VALID_REPLY]))

    response = service.triage(EMAIL)

    assert response.status == "ok"
    assert response.attempts == 1
    assert response.model == state.active_model
    assert response.failure_reason is None
    assert response.result.category == "delivery"
    assert response.latency_sec >= 0
    assert len(generate_calls(client)) == 1


def test_an_invalid_reply_is_retried_once_with_the_error_fed_back():
    service, client, _ = make_service(FakeClient(replies=[INVALID_REPLY, VALID_REPLY]))

    response = service.triage(EMAIL)

    assert response.status == "ok"
    assert response.attempts == 2
    first, second = generate_calls(client)
    assert "[SYSTEM FEEDBACK]" not in first[2]
    assert "[SYSTEM FEEDBACK]" in second[2]
    assert "priority" in second[2]
    assert second[2].startswith(first[2])


def test_two_invalid_replies_go_to_manual_review():
    service, client, _ = make_service(FakeClient(replies=[INVALID_REPLY, INVALID_REPLY]))

    response = service.triage(EMAIL)

    assert response.status == "needs_review"
    assert response.attempts == TRIAGE_MAX_ATTEMPTS == 2
    assert response.result is None
    assert response.failure_reason.startswith("Invalid model output after 2 attempts:")
    assert "priority" in response.failure_reason
    assert len(generate_calls(client)) == 2


def test_a_valid_reply_below_the_confidence_threshold_goes_to_manual_review():
    service, client, _ = make_service(FakeClient(replies=[LOW_CONFIDENCE_REPLY]))

    response = service.triage(EMAIL)

    assert response.status == "needs_review"
    assert response.attempts == 1
    assert response.result is not None
    assert response.result.confidence == 0.4
    assert f"below the {TRIAGE_CONFIDENCE_THRESHOLD:.2f} threshold" in response.failure_reason
    assert len(generate_calls(client)) == 1


def test_a_valid_reply_at_the_confidence_threshold_is_ok():
    at_threshold_reply = json.dumps({**json.loads(VALID_REPLY), "confidence": TRIAGE_CONFIDENCE_THRESHOLD})
    service, _, _ = make_service(FakeClient(replies=[at_threshold_reply]))

    response = service.triage(EMAIL)

    assert response.status == "ok"


def test_an_empty_reply_counts_as_invalid():
    service, _, _ = make_service(FakeClient(replies=[{"done": True}, ""]))

    response = service.triage(EMAIL)

    assert response.status == "needs_review"
    assert "Empty response" in response.failure_reason


def test_a_timeout_fails_at_once_without_a_retry():
    service, client, _ = make_service(FakeClient(replies=[LLMTimeoutError("slow"), VALID_REPLY]))

    response = service.triage(EMAIL)

    assert response.status == "failed"
    assert response.attempts == 1
    assert response.result is None
    assert f"{TRIAGE_TIMEOUT_SEC} s" in response.failure_reason
    assert len(generate_calls(client)) == 1


def test_a_timeout_on_the_retry_also_fails():
    service, _, _ = make_service(FakeClient(replies=[INVALID_REPLY, LLMTimeoutError("slow")]))

    response = service.triage(EMAIL)

    assert response.status == "failed"
    assert response.attempts == 2


def test_another_model_call_error_fails_with_its_message():
    service, client, _ = make_service(FakeClient(fail_on="generate"))

    response = service.triage(EMAIL)

    assert response.status == "failed"
    assert response.attempts == 1
    assert response.failure_reason == "The model call failed: generate failed"
    assert len(generate_calls(client)) == 1


@pytest.mark.parametrize("failing_call", ["list_loaded_models", "load_model"])
def test_a_model_loading_error_fails_without_generating(failing_call):
    service, client, _ = make_service(FakeClient(fail_on=failing_call, replies=[VALID_REPLY]))

    response = service.triage(EMAIL)

    assert response.status == "failed"
    assert response.attempts == 0
    assert response.failure_reason == f"Could not load the model: {failing_call} failed"
    assert generate_calls(client) == []


def test_other_models_are_unloaded_and_the_active_one_is_loaded_before_generating():
    client = FakeClient(replies=[VALID_REPLY], loaded=[f"{MODELS[1]}:latest", f"{MODELS[0]}:latest"])
    service, _, state = make_service(client)

    service.triage(EMAIL)

    assert [call[0] for call in client.calls] == ["list_loaded_models", "unload_model", "load_model", "generate"]
    assert client.calls[1] == ("unload_model", f"{MODELS[1]}:latest")
    assert client.calls[2] == ("load_model", state.active_model)


def test_generate_gets_the_active_settings_the_schema_and_the_timeout():
    service, client, state = make_service(FakeClient(replies=[VALID_REPLY]))
    state.active_model = MODELS[1]
    state.active_temperature = 0.0

    service.triage(EMAIL)

    ((_, model, prompt, temperature),) = generate_calls(client)
    assert (model, temperature) == (MODELS[1], 0.0)
    assert "Where is my parcel" in prompt and "Tracking says in transit." in prompt
    assert client.generate_options == [
        {"schema": TriageResult.model_json_schema(), "timeout": TRIAGE_TIMEOUT_SEC}
    ]
