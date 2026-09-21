import json

import pytest

from app.config import MAX_RETRIES
from app.schemas import UniversalResponse
from app.services import inference
from app.services.inference import FALLBACK_MESSAGE, run_inference_with_retry

MODEL = "test-model"
PROMPT = "Explain caching."
TEMPERATURE = 0.3
VALID_REPLY = json.dumps(
    {"reasoning": "step by step", "final_answer": "42", "confidence_score": 0.9}
)
INVALID_REPLY = json.dumps({"reasoning": "no answer given"})
FEEDBACK_MARKER = "[SYSTEM FEEDBACK]"
ZERO_METRICS = {
    "ttft_sec": 0,
    "latency_sec": 0,
    "tokens_per_sec": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "cpu_percent": 0,
    "ram_mb": 0,
    "vram_mb": 0,
}


class FakeStreamResponse:
    """Mimics the streaming Ollama response: a reply split over chunks, then a done line."""

    def __init__(self, reply: str, prompt_tokens: int = 12, output_tokens: int = 34):
        middle = len(reply) // 2
        self.lines = [
            {"response": reply[:middle], "done": False},
            {"response": reply[middle:], "done": False},
            {
                "response": "",
                "done": True,
                "prompt_eval_count": prompt_tokens,
                "eval_count": output_tokens,
            },
        ]

    def raise_for_status(self) -> None:
        pass

    def iter_lines(self):
        for line in self.lines:
            yield json.dumps(line).encode()


class OllamaStub:
    """Replays queued outcomes in order: a string is a model reply, an exception is raised."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.payloads = []

    def post(self, url, json=None, stream=False):
        self.payloads.append(json)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeStreamResponse(outcome)


@pytest.fixture
def stub_ollama(monkeypatch):
    def install(outcomes) -> OllamaStub:
        stub = OllamaStub(outcomes)
        monkeypatch.setattr(inference.requests, "post", stub.post)
        return stub

    monkeypatch.setattr(
        inference,
        "capture_process_usage",
        lambda: {"cpu_time": 1.0, "ram_mb": 100.0, "vram_mb": 0},
    )
    return install


def run():
    return run_inference_with_retry(MODEL, PROMPT, TEMPERATURE, UniversalResponse)


def test_valid_first_reply_succeeds_in_one_attempt(stub_ollama):
    stub = stub_ollama([VALID_REPLY])

    result = run()

    assert result["final_success"] is True
    assert result["total_attempts"] == 1
    assert result["message"] == "Success"
    assert result["reply"] == VALID_REPLY
    assert result["data"] == json.loads(VALID_REPLY)
    assert len(result["attempts_history"]) == 1
    record = result["attempts_history"][0]
    assert record["attempt"] == 1
    assert record["is_valid"] is True
    assert record["error"] is None
    assert record["input_tokens"] == 12
    assert record["output_tokens"] == 34
    assert record["ram_mb"] == 100.0
    assert stub.payloads == [
        {
            "model": MODEL,
            "prompt": PROMPT,
            "stream": True,
            "format": UniversalResponse.model_json_schema(),
            "options": {"temperature": TEMPERATURE},
        }
    ]


def test_invalid_reply_is_retried_with_validation_feedback(stub_ollama):
    stub = stub_ollama([INVALID_REPLY, VALID_REPLY])

    result = run()

    assert result["final_success"] is True
    assert result["total_attempts"] == 2
    first, second = result["attempts_history"]
    assert first["is_valid"] is False
    assert first["error"]
    assert second["is_valid"] is True
    retry_prompt = stub.payloads[1]["prompt"]
    assert retry_prompt.startswith(PROMPT)
    assert FEEDBACK_MARKER in retry_prompt
    assert first["error"] in retry_prompt
    assert second["prompt_used"] == retry_prompt


def test_never_valid_falls_back_after_max_retries(stub_ollama):
    replies = [json.dumps({"attempt": n}) for n in range(1, MAX_RETRIES + 1)]
    stub = stub_ollama(replies)

    result = run()

    assert result["final_success"] is False
    assert result["total_attempts"] == MAX_RETRIES
    assert result["data"] is None
    assert result["message"] == FALLBACK_MESSAGE
    assert result["reply"] == replies[-1]
    assert len(result["attempts_history"]) == MAX_RETRIES
    assert len(stub.payloads) == MAX_RETRIES
    # Feedback is rebuilt from the original prompt each time, so it never stacks.
    last_prompt = result["attempts_history"][-1]["prompt_used"]
    assert last_prompt.count(FEEDBACK_MARKER) == 1


def test_request_error_is_recorded_and_retried_without_feedback(stub_ollama):
    stub = stub_ollama([ConnectionError("connection refused"), VALID_REPLY])

    result = run()

    assert result["final_success"] is True
    assert result["total_attempts"] == 2
    failed = result["attempts_history"][0]
    assert failed["attempt"] == 1
    assert failed["is_valid"] is False
    assert failed["error"] == "connection refused"
    assert failed["reply"] == "connection refused"
    assert {key: failed[key] for key in ZERO_METRICS} == ZERO_METRICS
    assert stub.payloads[1]["prompt"] == PROMPT
    assert FEEDBACK_MARKER not in stub.payloads[1]["prompt"]


def test_every_attempt_failing_returns_last_error_as_reply(stub_ollama):
    errors = [ConnectionError(f"down {n}") for n in range(1, MAX_RETRIES + 1)]
    stub_ollama(errors)

    result = run()

    assert result["final_success"] is False
    assert result["total_attempts"] == MAX_RETRIES
    assert result["data"] is None
    assert result["message"] == FALLBACK_MESSAGE
    assert result["reply"] == f"down {MAX_RETRIES}"
    assert [record["is_valid"] for record in result["attempts_history"]] == [False] * MAX_RETRIES
