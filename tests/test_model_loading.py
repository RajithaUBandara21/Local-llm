import pytest

from app.services.model_loading import unload_others
from tests.fakes import FakeClient


def unloaded(client):
    return [call[1] for call in client.calls if call[0] == "unload_model"]


def test_nothing_loaded_means_nothing_to_unload():
    client = FakeClient(loaded=[])

    unload_others(client, "llama3.2")

    assert client.calls == [("list_loaded_models",)]


def test_only_the_target_loaded_means_nothing_to_unload():
    client = FakeClient(loaded=["llama3.2:latest"])

    unload_others(client, "llama3.2")

    assert unloaded(client) == []


def test_every_other_loaded_model_is_unloaded_by_its_reported_name():
    client = FakeClient(loaded=["phi-4-Q4:latest", "llama3.2:latest", "mistral-7b-q4:latest"])

    unload_others(client, "llama3.2")

    assert unloaded(client) == ["phi-4-Q4:latest", "mistral-7b-q4:latest"]


def test_models_outside_the_configured_list_are_unloaded_too():
    client = FakeClient(loaded=["not-configured:latest"])

    unload_others(client, "llama3.2")

    assert unloaded(client) == ["not-configured:latest"]


def test_models_that_differ_only_by_quantization_are_different_models():
    client = FakeClient(loaded=["mistral-7b-Q5:latest"])

    unload_others(client, "mistral-7b-q4")

    assert unloaded(client) == ["mistral-7b-Q5:latest"]


def test_a_tag_other_than_latest_is_a_different_model():
    client = FakeClient(loaded=["llama3.2:1b"])

    unload_others(client, "llama3.2")

    assert unloaded(client) == ["llama3.2:1b"]


@pytest.mark.parametrize("failing_call", ["list_loaded_models", "unload_model"])
def test_client_failures_propagate(failing_call):
    client = FakeClient(fail_on=failing_call, loaded=["phi-4-Q4:latest"])

    with pytest.raises(RuntimeError, match=f"{failing_call} failed"):
        unload_others(client, "llama3.2")
