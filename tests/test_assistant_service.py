import pytest
from fastapi import HTTPException

from app.clients.base import ILLMClient
from app.config import MODELS
from app.services.assistant import AssistantService
from app.state import AppState


class FakeClient(ILLMClient):
    """Records calls; a failure can be queued for any method."""

    def __init__(self, reply=None, fail_on=None):
        self.reply = reply or {"response": "hello"}
        self.fail_on = fail_on
        self.calls = []

    def _record(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_on == name:
            raise RuntimeError(f"{name} failed")

    def generate(self, model, prompt, temperature):
        self._record("generate", model, prompt, temperature)
        return self.reply

    def load_model(self, model):
        self._record("load_model", model)

    def unload_model(self, model):
        self._record("unload_model", model)


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
    assert client.calls == [("generate", MODELS[1], "hi", 0.2)]


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
    assert error.value.detail == "Model not-installed not configured."
    assert client.calls == []
    assert state.active_model == before


def test_switch_unloads_the_active_model_then_loads_the_new_one():
    service, client, state = make_service()
    previous = state.active_model

    assert service.switch_active_model(MODELS[1]) == MODELS[1]

    assert client.calls == [("unload_model", previous), ("load_model", MODELS[1])]
    assert state.active_model == MODELS[1]


@pytest.mark.parametrize("failing_call", ["unload_model", "load_model"])
def test_switch_failure_gives_500_and_keeps_the_active_model(failing_call):
    service, _, state = make_service(FakeClient(fail_on=failing_call))
    before = state.active_model

    with pytest.raises(HTTPException) as error:
        service.switch_active_model(MODELS[1])

    assert error.value.status_code == 500
    assert error.value.detail == f"Failed to switch models: {failing_call} failed"
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
