from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import BatchRequest, BatchStatus, LoadedEmail, StoredEmail


def test_a_batch_request_needs_a_file_name():
    assert BatchRequest(file="  northport_emails.csv ").file == "northport_emails.csv"


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_file_name_is_rejected(value):
    with pytest.raises(ValidationError):
        BatchRequest(file=value)


def test_a_batch_status_serializes_with_its_counts():
    created = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)

    status = BatchStatus(
        id=1, source_file="northport_emails.csv", status="running", total=100,
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
    email = StoredEmail(id=7, sender="a@example.com", subject="s", body_clean="b", received_at=None, mailbox=None)

    assert isinstance(email, LoadedEmail)
    assert email.id == 7
