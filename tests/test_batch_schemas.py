from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import BatchRequest, BatchStatus, LoadedEmail, ReviewActionRequest, StoredEmail


def test_a_batch_request_needs_a_file_name():
    assert BatchRequest(file="  northport_emails.csv ").file == "northport_emails.csv"


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_file_name_is_rejected(value):
    with pytest.raises(ValidationError):
        BatchRequest(file=value)


def test_a_batch_status_serializes_with_its_counts():
    created = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)

    status = BatchStatus(
        id=1, source_file="northport_emails.csv", display_name="northport_emails.csv", status="running", total=100,
        processed=3, ok=2, needs_review=1, failed=0, created_at=created,
    )

    data = status.model_dump(mode="json")
    assert data["active"] is False
    assert data["finished_at"] is None
    assert data["created_at"] == "2026-03-02T08:00:00Z"
    assert data["ok"] + data["needs_review"] + data["failed"] == data["processed"]


def test_a_batch_status_rejects_an_unknown_status():
    with pytest.raises(ValidationError):
        BatchStatus(
            id=1, source_file="a.csv", status="paused", total=1, processed=0,
            ok=0, needs_review=0, failed=0, created_at=datetime.now(timezone.utc),
        )


def test_a_stored_email_is_a_loaded_email_with_an_id():
    email = StoredEmail(id=7, sender="a@example.com", subject="s", body_clean="b", received_at=None)

    assert isinstance(email, LoadedEmail)
    assert email.id == 7


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_approve_and_reject_need_no_edited_reply(action):
    assert ReviewActionRequest(action=action).edited_reply is None


def test_edit_needs_a_non_blank_edited_reply():
    assert ReviewActionRequest(action="edit", edited_reply="Here is the fix.").edited_reply == "Here is the fix."


@pytest.mark.parametrize("edited_reply", [None, "", "   "])
def test_edit_without_a_real_edited_reply_is_rejected(edited_reply):
    with pytest.raises(ValidationError):
        ReviewActionRequest(action="edit", edited_reply=edited_reply)


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_an_edited_reply_on_approve_or_reject_is_rejected(action):
    with pytest.raises(ValidationError):
        ReviewActionRequest(action=action, edited_reply="Should not be here.")
