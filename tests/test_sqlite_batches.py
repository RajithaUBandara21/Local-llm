import json
import sqlite3
from datetime import datetime, timezone

import pytest

from app.repositories.sqlite_batches import SQLiteBatchRepository
from app.schemas import LoadedEmail, TriageResponse, TriageResult


def make_email(number: int) -> LoadedEmail:
    return LoadedEmail(
        sender=f"sender{number}@example.com",
        subject=f"Subject {number}",
        body_clean=f"Body {number}",
        received_at=datetime(2026, 3, 2, 8, number, tzinfo=timezone.utc),
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
    batch_id = repo.create_batch("mail.csv", [make_email(1), make_email(2), make_email(3)])

    pending = repo.pending_emails(batch_id)

    assert [email.subject for email in pending] == ["Subject 1", "Subject 2", "Subject 3"]
    assert pending[0].id < pending[1].id < pending[2].id
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


def test_pending_mailbox_files_are_listed_newest_first_until_discarded(repo):
    repo.save_pending_mailbox_file("upload-a.csv", "Week 1 inbox")
    repo.save_pending_mailbox_file("upload-b.csv", "Week 2 inbox")

    pending = repo.list_pending_mailbox_files()

    assert [p.file for p in pending] == ["upload-b.csv", "upload-a.csv"]
    assert pending[0].display_name == "Week 2 inbox"

    repo.delete_pending_mailbox_file("upload-a.csv")
    assert [p.file for p in repo.list_pending_mailbox_files()] == ["upload-b.csv"]

    repo.delete_pending_mailbox_file("upload-a.csv")  # no-op the second time
    assert [p.file for p in repo.list_pending_mailbox_files()] == ["upload-b.csv"]


def test_creating_a_batch_clears_its_pending_mailbox_file_record(repo):
    repo.save_pending_mailbox_file("mail.csv", "My inbox")

    batch_id = repo.create_batch("mail.csv", [make_email(1)])

    assert repo.list_pending_mailbox_files() == []
    assert repo.get_batch(batch_id).display_name == "My inbox"


def test_creating_a_batch_with_no_pending_record_falls_back_to_the_source_file(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])

    assert repo.get_batch(batch_id).display_name == "mail.csv"


def test_list_batches_limit_and_offset_page_through_newest_first(repo):
    first = repo.create_batch("a.csv", [make_email(1)])
    second = repo.create_batch("b.csv", [make_email(2)])
    third = repo.create_batch("c.csv", [make_email(3)])

    assert [batch.id for batch in repo.list_batches(limit=2)] == [third, second]
    assert [batch.id for batch in repo.list_batches(limit=2, offset=2)] == [first]
    assert repo.list_batches(limit=2, offset=4) == []


def test_list_emails_limit_and_offset_page_through_id_order(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(n) for n in range(1, 5)])

    page = repo.list_emails(batch_id, limit=2)
    next_page = repo.list_emails(batch_id, limit=2, offset=2)

    assert [email.subject for email in page] == ["Subject 1", "Subject 2"]
    assert [email.subject for email in next_page] == ["Subject 3", "Subject 4"]
    assert repo.list_emails(batch_id, limit=2, offset=4) == []


def test_a_batch_survives_a_new_repository_on_the_same_file(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])

    reopened = SQLiteBatchRepository(repo.path)

    assert reopened.get_batch(batch_id).total == 1
    assert len(reopened.pending_emails(batch_id)) == 1


def test_a_database_from_before_display_name_existed_is_migrated_in_place(tmp_path):
    db_path = tmp_path / "old.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE batches (id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT NOT NULL, "
            "total INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT)"
        )
        db.execute(
            "INSERT INTO batches (source_file, total, status, created_at) VALUES (?, ?, 'running', ?)",
            ("old.csv", 1, "2026-01-01T00:00:00+00:00"),
        )
        batch_id = db.execute("SELECT id FROM batches").fetchone()[0]

    repo = SQLiteBatchRepository(db_path)

    assert repo.get_batch(batch_id).display_name == "old.csv"


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


def test_list_emails_returns_every_email_in_id_order(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1), make_email(2), make_email(3)])

    emails = repo.list_emails()

    assert [email.subject for email in emails] == ["Subject 1", "Subject 2", "Subject 3"]
    assert {email.batch_id for email in emails} == {batch_id}


def test_list_emails_can_be_narrowed_to_one_batch(repo):
    first = repo.create_batch("a.csv", [make_email(1)])
    second = repo.create_batch("b.csv", [make_email(2)])

    assert [email.subject for email in repo.list_emails(second)] == ["Subject 2"]
    assert [email.subject for email in repo.list_emails(first)] == ["Subject 1"]
    assert len(repo.list_emails()) == 2
    assert repo.list_emails(999) == []


def test_list_emails_rebuilds_each_stored_outcome(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(n) for n in range(1, 5)])
    ok, review, failed, unprocessed = repo.pending_emails(batch_id)
    repo.save_result(ok.id, ok_response(flags=["stale_context"], flag_reason="Old order.", confidence=0.6))
    repo.save_result(review.id, failed_response("needs_review", "Invalid model output after 2 attempts: x"))
    repo.save_result(failed.id, failed_response())

    emails = repo.list_emails()

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


def test_an_email_with_no_review_action_has_none(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])
    (email,) = repo.pending_emails(batch_id)

    assert repo.get_email(email.id).review is None
    assert repo.list_emails()[0].review is None


def test_a_saved_review_action_appears_as_the_latest_on_both_reads(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])
    (email,) = repo.pending_emails(batch_id)

    saved = repo.save_review_action(email.id, "approve", None)

    assert (saved.email_id, saved.action, saved.edited_reply) == (email.id, "approve", None)
    for review in (repo.get_email(email.id).review, repo.list_emails()[0].review):
        assert (review.id, review.action) == (saved.id, "approve")


def test_a_second_review_action_becomes_the_latest_and_the_first_is_kept(repo):
    batch_id = repo.create_batch("mail.csv", [make_email(1)])
    (email,) = repo.pending_emails(batch_id)
    repo.save_review_action(email.id, "reject", None)

    second = repo.save_review_action(email.id, "edit", "Here is the corrected reply.")

    assert repo.get_email(email.id).review.id == second.id
    assert (repo.get_email(email.id).review.action, repo.get_email(email.id).review.edited_reply) == (
        "edit", "Here is the corrected reply.",
    )
    assert [row["action"] for row in rows(repo, "SELECT action FROM review_actions ORDER BY id")] == [
        "reject", "edit",
    ]


def test_get_email_is_none_for_an_unknown_id(repo):
    assert repo.get_email(999) is None
