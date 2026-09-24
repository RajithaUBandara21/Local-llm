import pytest
from fastapi import HTTPException

from app.config import MODELS
from app.services.assistant import AssistantService
from app.state import AppState
from tests.fakes import FakeClient


def make_service(client=None):
    client = client or FakeClient()
    state = AppState()
    return AssistantService(client, state), client, state


def test_chat_uses_active_model_and_temperature():
    service, client, state = make_service()
    state.active_model = MODELS[1]
    state.active_temperature = 0.2

    reply = service.process_chat("hi")

    assert reply == {"response": "hello"}
    assert client.calls == [("list_loaded_models",), ("generate", MODELS[1], "hi", 0.2)]


def test_chat_unloads_another_loaded_model_before_generating():
    service, client, state = make_service(FakeClient(loaded=[f"{MODELS[1]}:latest", f"{MODELS[0]}:latest"]))
    state.active_model = MODELS[0]

    service.process_chat("hi")

    assert client.calls == [
        ("list_loaded_models",),
        ("unload_model", f"{MODELS[1]}:latest"),
        ("generate", MODELS[0], "hi", state.active_temperature),
    ]


@pytest.mark.parametrize("failing_call", ["list_loaded_models", "unload_model"])
def test_chat_stops_before_generating_when_exclusivity_fails(failing_call):
    client = FakeClient(fail_on=failing_call, loaded=[f"{MODELS[1]}:latest"])
    service, _, state = make_service(client)
    state.active_model = MODELS[0]

    with pytest.raises(HTTPException) as error:
        service.process_chat("hi")

    assert error.value.status_code == 500
    assert error.value.detail == f"LLM Generation failed: {failing_call} failed"
    assert ("generate", MODELS[0], "hi", state.active_temperature) not in client.calls


def test_chat_failure_is_wrapped_in_500():
    service, _, _ = make_service(FakeClient(fail_on="generate"))

    with pytest.raises(HTTPException) as error:
        service.process_chat("hi")

    assert error.value.status_code == 500
    assert error.value.detail == "LLM Generation failed: generate failed"


def test_unknown_model_is_rejected_without_touching_the_client():
    service, client, state = make_service()
    before = state.active_model

    with pytest.raises(HTTPException) as error:
        service.switch_active_model("not-installed")

    assert error.value.status_code == 400
    assert error.value.detail == "Model not-installed is not installed in Ollama."
    assert client.calls == [("list_available_models",)]
    assert state.active_model == before


def test_active_settings_reflects_state():
    service, _, state = make_service()
    state.active_model = MODELS[1]
    state.active_temperature = 0.4

    assert service.active_settings() == (MODELS[1], 0.4)


def test_list_available_models_returns_what_ollama_has_installed():
    service, client, _ = make_service(FakeClient(available=["llama3.2", "phi-4-Q4"]))

    assert service.list_available_models() == ["llama3.2", "phi-4-Q4"]
    assert client.calls == [("list_available_models",)]


def test_list_available_models_failure_is_wrapped_in_500():
    service, _, _ = make_service(FakeClient(fail_on="list_available_models"))

    with pytest.raises(HTTPException) as error:
        service.list_available_models()

    assert error.value.status_code == 500
    assert error.value.detail == "Failed to list installed models: list_available_models failed"


def test_switch_unloads_every_other_loaded_model_then_loads_the_new_one():
    loaded = [f"{MODELS[0]}:latest", "not-configured:latest", f"{MODELS[1]}:latest"]
    service, client, state = make_service(FakeClient(loaded=loaded))

    assert service.switch_active_model(MODELS[1]) == MODELS[1]

    assert client.calls == [
        ("list_available_models",),
        ("list_loaded_models",),
        ("unload_model", f"{MODELS[0]}:latest"),
        ("unload_model", "not-configured:latest"),
        ("load_model", MODELS[1]),
    ]
    assert state.active_model == MODELS[1]


@pytest.mark.parametrize("failing_call", ["list_loaded_models", "unload_model", "load_model"])
def test_switch_failure_gives_500_and_keeps_the_active_model(failing_call):
    service, _, state = make_service(FakeClient(fail_on=failing_call, loaded=[f"{MODELS[0]}:latest"]))
    before = state.active_model

    with pytest.raises(HTTPException) as error:
        service.switch_active_model(MODELS[1])

    assert error.value.status_code == 500
    assert error.value.detail == f"Failed to switch models: {failing_call} failed"
    assert state.active_model == before


def test_switch_to_a_model_when_listing_available_models_fails_gives_500():
    service, _, state = make_service(FakeClient(fail_on="list_available_models"))
    before = state.active_model

    with pytest.raises(HTTPException) as error:
        service.switch_active_model(MODELS[1])

    assert error.value.status_code == 500
    assert error.value.detail == "Failed to list installed models: list_available_models failed"
    assert state.active_model == before


@pytest.mark.parametrize("temperature", [0.0, 0.7, 2.0])
def test_temperature_inside_the_range_is_stored(temperature):
    service, _, state = make_service()

    assert service.update_temperature(temperature) == temperature
    assert state.active_temperature == temperature


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_temperature_outside_the_range_is_rejected(temperature):
    service, _, state = make_service()

    with pytest.raises(HTTPException) as error:
        service.update_temperature(temperature)

    assert error.value.status_code == 400
    assert error.value.detail == "Temperature must be between 0.0 and 2.0"
    assert state.active_temperature == 0.7
