import json

import pytest
from pydantic import ValidationError

from app.config import TRIAGE_MAX_BODY_CHARS
from app.schemas import TriageRequest, TriageResult
from app.services.output_validator import OutputValidator


def result_fields(**overrides):
    fields = {
        "category": "delivery",
        "priority": "normal",
        "summary": "Customer asks where parcel NP48213907 is.",
        "suggested_reply": "Hello, thanks for writing. We are checking the tracking now.",
        "confidence": 0.8,
        "flags": [],
        "flag_reason": None,
    }
    fields.update(overrides)
    return fields


def test_a_valid_reply_passes_the_output_validator():
    is_valid, data, error = OutputValidator.validate_json(json.dumps(result_fields()), TriageResult)

    assert (is_valid, error) == (True, None)
    assert data["category"] == "delivery"
    assert data["flags"] == []


def test_flags_and_flag_reason_may_be_left_out():
    fields = result_fields()
    del fields["flags"], fields["flag_reason"]

    result = TriageResult(**fields)

    assert result.flags == []
    assert result.flag_reason is None


def test_a_stale_context_flag_keeps_its_draft_and_needs_a_reason():
    result = TriageResult(**result_fields(flags=["stale_context"], flag_reason="Refers to an order from last year."))

    assert result.flags == ["stale_context"]
    assert result.suggested_reply


def test_an_out_of_policy_reply_has_no_draft_and_a_reason():
    result = TriageResult(
        **result_fields(suggested_reply=None, flags=["out_of_policy"], flag_reason="Asks for legal advice.")
    )

    assert result.suggested_reply is None


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"category": "shipping"}, "category"),
        ({"priority": "critical"}, "priority"),
        ({"flags": ["spammy"], "flag_reason": "x"}, "flags"),
        ({"confidence": 1.2}, "confidence"),
        ({"confidence": -0.1}, "confidence"),
        ({"summary": "   "}, "summary"),
        ({"flags": ["stale_context"]}, "flag_reason is required"),
        ({"flags": ["stale_context"], "flag_reason": "  "}, "flag_reason is required"),
        ({"flag_reason": "no flags but a reason"}, "flag_reason must be null"),
        (
            {"flags": ["out_of_policy"], "flag_reason": "Legal advice."},
            "suggested_reply must be null",
        ),
        ({"suggested_reply": None}, "suggested_reply is required"),
        ({"suggested_reply": "  "}, "suggested_reply is required"),
    ],
)
def test_a_result_that_breaks_a_rule_is_rejected(overrides, message):
    with pytest.raises(ValidationError, match=message):
        TriageResult(**result_fields(**overrides))


def test_a_missing_required_field_is_rejected():
    fields = result_fields()
    del fields["suggested_reply"]

    with pytest.raises(ValidationError, match="suggested_reply"):
        TriageResult(**fields)


def test_the_request_needs_only_a_body():
    request = TriageRequest(body="  Where is my parcel?  ")

    assert request.body == "Where is my parcel?"
    assert request.subject == ""
    assert request.sender is None


@pytest.mark.parametrize("body", ["", "   \n\t"])
def test_a_blank_body_is_rejected(body):
    with pytest.raises(ValidationError):
        TriageRequest(body=body)


def test_a_body_over_the_cap_is_rejected():
    assert TriageRequest(body="a" * TRIAGE_MAX_BODY_CHARS)

    with pytest.raises(ValidationError):
        TriageRequest(body="a" * (TRIAGE_MAX_BODY_CHARS + 1))
