import pytest
import requests

from app.clients import ollama
from app.clients.base import LLMTimeoutError
from app.clients.ollama import OllamaClient

GENERATE_URL = "http://ollama.test/api/generate"
SCHEMA = {"type": "object", "properties": {"category": {"type": "string"}}}


class StubResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


@pytest.fixture
def posts(monkeypatch):
    """Captures each requests.post call and replies with a fixed Ollama body."""
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return StubResponse({"response": "hi"})

    monkeypatch.setattr(ollama.requests, "post", fake_post)
    return calls


def make_client():
    return OllamaClient(GENERATE_URL, "http://ollama.test/api/ps")


def test_generate_without_a_schema_sends_no_format_and_no_timeout(posts):
    reply = make_client().generate("llama3.2", "hello", 0.3)

    assert reply == {"response": "hi"}
    ((url, kwargs),) = posts
    assert url == GENERATE_URL
    assert kwargs["json"] == {
        "model": "llama3.2", "prompt": "hello", "stream": False, "options": {"temperature": 0.3}
    }
    assert kwargs["timeout"] is None


def test_generate_sends_the_schema_as_format_and_forwards_the_timeout(posts):
    make_client().generate("llama3.2", "hello", 0.0, schema=SCHEMA, timeout=30)

    ((_, kwargs),) = posts
    assert kwargs["json"]["format"] == SCHEMA
    assert kwargs["timeout"] == 30


@pytest.mark.parametrize("error", [requests.ReadTimeout, requests.ConnectTimeout])
def test_a_request_timeout_becomes_an_llm_timeout(monkeypatch, error):
    def raise_timeout(url, **kwargs):
        raise error("slow")

    monkeypatch.setattr(ollama.requests, "post", raise_timeout)

    with pytest.raises(LLMTimeoutError, match="within 30 s"):
        make_client().generate("llama3.2", "hello", 0.0, timeout=30)


def test_other_request_errors_are_not_reported_as_timeouts(monkeypatch):
    def refuse(url, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(ollama.requests, "post", refuse)

    with pytest.raises(requests.ConnectionError):
        make_client().generate("llama3.2", "hello", 0.0, timeout=30)
