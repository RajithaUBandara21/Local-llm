import json

from config import UniversalResponse
from validator import OutputValidator

VALID_REPLY = {"reasoning": "step by step", "final_answer": "42", "confidence_score": 0.9}


class ExplodingSchema:
    """Stands in for a schema class whose parsing fails outside Pydantic's own errors."""

    @staticmethod
    def model_validate_json(_text: str):
        raise RuntimeError("boom")


def test_valid_json_returns_dumped_data():
    is_valid, data, error = OutputValidator.validate_json(json.dumps(VALID_REPLY), UniversalResponse)

    assert is_valid is True
    assert data == VALID_REPLY
    assert error is None


def test_empty_response_is_rejected():
    result = OutputValidator.validate_json("", UniversalResponse)

    assert result == (False, None, "Empty response received from the model.")


def test_malformed_json_is_a_validation_error():
    is_valid, data, error = OutputValidator.validate_json("{not json", UniversalResponse)

    assert is_valid is False
    assert data is None
    assert error.startswith("Pydantic Validation Error")


def test_missing_required_field_is_a_validation_error():
    reply = {k: v for k, v in VALID_REPLY.items() if k != "final_answer"}

    is_valid, data, error = OutputValidator.validate_json(json.dumps(reply), UniversalResponse)

    assert is_valid is False
    assert data is None
    assert error.startswith("Pydantic Validation Error")
    assert "final_answer" in error


def test_wrong_field_type_is_a_validation_error():
    reply = {**VALID_REPLY, "confidence_score": "very sure"}

    is_valid, data, error = OutputValidator.validate_json(json.dumps(reply), UniversalResponse)

    assert is_valid is False
    assert data is None
    assert error.startswith("Pydantic Validation Error")
    assert "confidence_score" in error


def test_non_pydantic_failure_is_reported_as_unexpected():
    is_valid, data, error = OutputValidator.validate_json("{}", ExplodingSchema)

    assert is_valid is False
    assert data is None
    assert error == "Unexpected Parsing Error: boom"
