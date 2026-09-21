import json
import sqlite3
from datetime import datetime, timezone

import pytest

from app.repositories.sqlite_batches import SQLiteBatchRepository
from app.schemas import LoadedEmail, TriageResponse, TriageResult


def make_email(number: int, mailbox: str | None = "support") -> LoadedEmail:
    return LoadedEmail(
        sender=f"sender{number}@example.com",
        subject=f"Subject {number}",
        body_clean=f"Body {number}",
        received_at=datetime(2026, 3, 2, 8, number, tzinfo=timezone.utc),
        mailbox=mailbox,
    )


def make_result(**overrides) -> TriageResult:
    fields = {
        "category": "delivery",
        "priority": "normal",
        "summary": "Asks where the parcel is.",
        "suggested_reply": "We are checking the tracking.",
        "confidence": 0.8,
        "flags": [],
        "flag_reason": None,
    }
    fields.update(overrides)
    return TriageResult(**fields)


def ok_response(**result_overrides) -> TriageResponse:
    return TriageResponse(
        status="ok", model="llama3.2", attempts=1, latency_sec=1.25, result=make_result(**result_overrides)
    )


def failed_response(status="failed", reason="The model did not answer within 30 s.") -> TriageResponse:
    return TriageResponse(status=status, model="llama3.2", attempts=1, latency_sec=30.0, failure_reason=reason)


@pytest.fixture
def repo(tmp_path):
    return SQLiteBatchRepository(tmp_path / "triage.db")


def rows(repo, sql, *params):
    connection = sqlite3.connect(repo.path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql, params)]
    finally:
        connection.close()


def test_a_new_batch_is_running_with_zero_counts(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1), make_email(2)])

    batch = repo.get_batch(batch_id)

    assert (batch.id, batch.source_file, batch.status, batch.total) == (batch_id, "mail.csv", "running", 2)
    assert (batch.processed, batch.ok, batch.needs_review, batch.failed) == (0, 0, 0, 0)
    assert batch.finished_at is None
    assert batch.active is False


def test_emails_are_stored_in_file_order_and_all_pending(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1), make_email(2, mailbox=None), make_email(3)])

    pending = repo.pending_emails(batch_id)

    assert [email.subject for email in pending] == ["Subject 1", "Subject 2", "Subject 3"]
    assert pending[0].id < pending[1].id < pending[2].id
    assert pending[1].mailbox is None
    assert pending[0].received_at == datetime(2026, 3, 2, 8, 1, tzinfo=timezone.utc)


def test_an_email_without_a_received_time_is_stored_as_null(repo):
    email = make_email(1).model_copy(update={"received_at": None})

    batch_id = repo.create_batch("mail.csv", [email])

    assert repo.pending_emails(batch_id)[0].received_at is None


def test_an_unknown_batch_is_none_and_has_no_pending_emails(repo):
    assert repo.get_batch(99) is None
    assert repo.pending_emails(99) == []


def test_batches_list_newest_first_and_only_see_their_own_emails(repo):
    first = repo.create_batch("a.csv", [make_email(1)])
    second = repo.create_batch("b.csv", [make_email(2), make_email(3)])

    assert [batch.id for batch in repo.list_batches()] == [second, first]
    assert [email.subject for email in repo.pending_emails(first)] == ["Subject 1"]


def test_a_batch_survives_a_new_repository_on_the_same_file(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])

    reopened = SQLiteBatchRepository(repo.path)

    assert reopened.get_batch(batch_id).total == 1
    assert len(reopened.pending_emails(batch_id)) == 1


def test_the_parent_directory_is_created(tmp_path):
    repo = SQLiteBatchRepository(tmp_path / "nested" / "dir" / "triage.db")

    assert repo.list_batches() == []


def test_saved_results_feed_the_counts_and_shrink_the_pending_list(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(n) for n in range(1, 5)])
    first, second, third, fourth = repo.pending_emails(batch_id)

    repo.save_result(first.id, ok_response())
    repo.save_result(second.id, failed_response("needs_review", "Invalid model output after 2 attempts: x"))
    repo.save_result(third.id, failed_response())

    batch = repo.get_batch(batch_id)
    assert (batch.processed, batch.ok, batch.needs_review, batch.failed) == (3, 1, 1, 1)
    assert [email.id for email in repo.pending_emails(batch_id)] == [fourth.id]


def test_an_ok_result_is_stored_with_its_fields_and_flags_as_json(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])
    (email,) = repo.pending_emails(batch_id)

    repo.save_result(
        email.id,
        ok_response(flags=["stale_context"], flag_reason="Refers to an old order.", confidence=0.6),
    )

    (row,) = rows(repo, "SELECT * FROM triage_results")
    assert row["email_id"] == email.id
    assert (row["model"], row["status"], row["attempts"], row["latency_sec"]) == ("llama3.2", "ok", 1, 1.25)
    assert (row["category"], row["priority"], row["confidence"]) == ("delivery", "normal", 0.6)
    assert json.loads(row["flags"]) == ["stale_context"]
    assert row["flag_reason"] == "Refers to an old order."
    assert row["failure_reason"] is None


def test_a_failed_result_keeps_its_reason_and_no_result_columns(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])
    (email,) = repo.pending_emails(batch_id)

    repo.save_result(email.id, failed_response())

    (row,) = rows(repo, "SELECT * FROM triage_results")
    assert row["status"] == "failed"
    assert row["failure_reason"] == "The model did not answer within 30 s."
    assert (row["category"], row["summary"], row["flags"]) == (None, None, None)


def test_each_save_writes_one_decision_log_row(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1), make_email(2)])
    first, second = repo.pending_emails(batch_id)

    repo.save_result(first.id, ok_response())
    repo.save_result(second.id, failed_response())

    log = rows(repo, "SELECT email_id, model, latency_sec, outcome FROM decision_log ORDER BY id")
    assert log == [
        {"email_id": first.id, "model": "llama3.2", "latency_sec": 1.25, "outcome": "ok"},
        {"email_id": second.id, "model": "llama3.2", "latency_sec": 30.0, "outcome": "failed"},
    ]


def test_saving_again_replaces_the_result_and_logs_the_new_decision(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])
    (email,) = repo.pending_emails(batch_id)

    repo.save_result(email.id, failed_response())
    repo.save_result(email.id, ok_response())

    assert [row["status"] for row in rows(repo, "SELECT status FROM triage_results")] == ["ok"]
    assert [row["outcome"] for row in rows(repo, "SELECT outcome FROM decision_log ORDER BY id")] == ["failed", "ok"]
    assert repo.get_batch(batch_id).processed == 1


def test_a_result_for_an_unknown_email_leaves_no_partial_rows(repo):
    with pytest.raises(sqlite3.IntegrityError):
        repo.save_result(999, ok_response())

    assert rows(repo, "SELECT * FROM triage_results") == []
    assert rows(repo, "SELECT * FROM decision_log") == []


def test_mark_completed_sets_the_status_and_time(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])
    other = repo.create_batch("other.csv", [make_email(2)])

    repo.mark_completed(batch_id)

    batch = repo.get_batch(batch_id)
    assert batch.status == "completed"
    assert batch.finished_at is not None
    assert repo.get_batch(other).status == "running"


def test_values_are_bound_not_formatted_into_sql(repo):
    tricky = make_email(1).model_copy(update={"subject": "x'); DROP TABLE emails; --"})

    batch_id = repo.create_batch("mail.csv", [tricky])

    assert repo.pending_emails(batch_id)[0].subject == "x'); DROP TABLE emails; --"
    assert rows(repo, "SELECT COUNT(*) AS n FROM emails")[0]["n"] == 1


def test_a_mailbox_read_returns_only_that_mailbox_in_email_order(repo):
    batch_id = repo.create_batch(
        "mail.csv",
        [make_email(1, "support"), make_email(2, "refunds"), make_email(3, "support"), make_email(4, None)],
    )

    emails = repo.list_mailbox_emails("support")

    assert [email.subject for email in emails] == ["Subject 1", "Subject 3"]
    assert {email.mailbox for email in emails} == {"support"}
    assert {email.batch_id for email in emails} == {batch_id}
    assert repo.list_mailbox_emails("nowhere") == []


def test_an_email_with_no_mailbox_is_never_returned(repo):
    repo.create_batch("mail.mbox", [make_email(1, None)])

    assert repo.list_mailbox_emails("None") == []
    assert repo.list_mailbox_emails("") == []


def test_a_mailbox_read_can_be_narrowed_to_one_batch(repo):
    first = repo.create_batch("a.csv", [make_email(1, "support")])
    second = repo.create_batch("b.csv", [make_email(2, "support")])

    assert [email.subject for email in repo.list_mailbox_emails("support", second)] == ["Subject 2"]
    assert [email.subject for email in repo.list_mailbox_emails("support", first)] == ["Subject 1"]
    assert len(repo.list_mailbox_emails("support")) == 2
    assert repo.list_mailbox_emails("support", 999) == []


def test_a_mailbox_read_rebuilds_each_stored_outcome(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(n, "support") for n in range(1, 5)])
    ok, review, failed, unprocessed = repo.pending_emails(batch_id)
    repo.save_result(ok.id, ok_response(flags=["stale_context"], flag_reason="Old order.", confidence=0.6))
    repo.save_result(review.id, failed_response("needs_review", "Invalid model output after 2 attempts: x"))
    repo.save_result(failed.id, failed_response())

    emails = repo.list_mailbox_emails("support")

    by_id = {email.id: email for email in emails}
    assert by_id[ok.id].triage.status == "ok"
    assert by_id[ok.id].triage.result.flags == ["stale_context"]
    assert by_id[ok.id].triage.result.category == "delivery"
    assert by_id[ok.id].triage.latency_sec == 1.25
    assert by_id[review.id].triage.status == "needs_review"
    assert by_id[review.id].triage.result is None
    assert by_id[review.id].triage.failure_reason.startswith("Invalid model output")
    assert by_id[failed.id].triage.status == "failed"
    assert by_id[failed.id].triage.attempts == 1
    assert by_id[unprocessed.id].triage is None
