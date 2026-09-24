import json
import sqlite3
import threading
import time
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.clients.base import LLMTimeoutError
from app.config import TRIAGE_MAX_BODY_CHARS
from app.repositories.sqlite_batches import SQLiteBatchRepository
from app.services import batch as batch_module
from app.services.batch import BatchService
from app.services.triage import TriageService
from app.state import AppState
from tests.fakes import FakeClient

VALID_REPLY = json.dumps({
    "category": "delivery",
    "priority": "normal",
    "summary": "Customer asks where the parcel is.",
    "suggested_reply": "Thanks for writing, we are checking the tracking.",
    "confidence": 0.9,
    "flags": [],
    "flag_reason": None,
})
INVALID_REPLY = json.dumps({"category": "delivery", "priority": "asap"})
HEADER = "sender,subject,body,received_at\n"


class Crash(BaseException):
    """Stands in for a killed process: not an Exception, so nothing in the pipeline catches it."""


def csv_text(bodies):
    rows = [f'a{n}@example.com,Subject {n},"{body}",2026-03-02T08:00:00+00:00\n' for n, body in enumerate(bodies, 1)]
    return HEADER + "".join(rows)


@pytest.fixture
def mailbox_dir(tmp_path):
    folder = tmp_path / "mail"
    folder.mkdir()
    (folder / "four.csv").write_text(csv_text(["one", "two", "three", "four"]), encoding="utf-8")
    return folder


def make_service(tmp_path, mailbox_dir, client=None, state=None):
    state = state or AppState()
    client = client or FakeClient()
    db_path = tmp_path / "triage.db"
    repo = SQLiteBatchRepository(db_path)
    return BatchService(repo, TriageService(client, state), state, mailbox_dir), client, state, repo


def generate_count(client):
    return len([call for call in client.calls if call[0] == "generate"])


def rows(repo, sql):
    connection = sqlite3.connect(repo.path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql)]
    finally:
        connection.close()


def test_start_stores_the_batch_and_claims_the_worker_slot(tmp_path, mailbox_dir):
    service, _, state, repo = make_service(tmp_path, mailbox_dir)

    batch = service.start("four.csv")

    assert (batch.source_file, batch.status, batch.total, batch.processed) == ("four.csv", "running", 4, 0)
    assert batch.active is True
    assert state.active_batch_id == batch.id
    assert [email.subject for email in repo.pending_emails(batch.id)] == [f"Subject {n}" for n in (1, 2, 3, 4)]


def test_a_full_run_stores_every_result_and_log_row_and_completes(tmp_path, mailbox_dir):
    client = FakeClient(replies=[VALID_REPLY] * 4)
    service, _, state, repo = make_service(tmp_path, mailbox_dir, client)
    batch = service.start("four.csv")

    service.run(batch.id)

    done = service.get(batch.id)
    assert (done.status, done.processed, done.ok, done.needs_review, done.failed) == ("completed", 4, 4, 0, 0)
    assert done.active is False and done.finished_at is not None
    assert state.active_batch_id is None
    assert len(rows(repo, "SELECT * FROM decision_log")) == 4
    assert generate_count(client) == 4


def test_a_bad_reply_and_a_timeout_do_not_stop_the_batch(tmp_path, mailbox_dir):
    replies = [VALID_REPLY, INVALID_REPLY, INVALID_REPLY, LLMTimeoutError("slow"), VALID_REPLY]
    service, client, _, _ = make_service(tmp_path, mailbox_dir, FakeClient(replies=replies))
    batch = service.start("four.csv")

    service.run(batch.id)

    done = service.get(batch.id)
    assert (done.status, done.processed) == ("completed", 4)
    assert (done.ok, done.needs_review, done.failed) == (2, 1, 1)


def test_results_are_saved_in_file_order(tmp_path, mailbox_dir):
    replies = [VALID_REPLY, LLMTimeoutError("slow"), VALID_REPLY, VALID_REPLY]
    service, _, _, repo = make_service(tmp_path, mailbox_dir, FakeClient(replies=replies))
    batch = service.start("four.csv")

    service.run(batch.id)

    statuses = [row["status"] for row in rows(repo, "SELECT status FROM triage_results ORDER BY email_id")]
    assert statuses == ["ok", "failed", "ok", "ok"]


def test_an_empty_or_over_long_email_goes_to_manual_review_without_a_model_call(tmp_path, mailbox_dir):
    (mailbox_dir / "odd.csv").write_text(
        csv_text(["   ", "x" * (TRIAGE_MAX_BODY_CHARS + 1), "fine"]), encoding="utf-8"
    )
    client = FakeClient(replies=[VALID_REPLY])
    service, _, _, repo = make_service(tmp_path, mailbox_dir, client)
    batch = service.start("odd.csv")

    service.run(batch.id)

    done = service.get(batch.id)
    assert (done.processed, done.ok, done.needs_review) == (3, 1, 2)
    assert generate_count(client) == 1
    reasons = [row["failure_reason"] for row in rows(repo, "SELECT failure_reason FROM triage_results ORDER BY email_id")]
    assert "body" in reasons[0] and "at least 1 character" in reasons[0]
    assert "body" in reasons[1] and "at most" in reasons[1]
    assert reasons[2] is None


def test_a_crash_leaves_the_batch_resumable_and_resume_skips_finished_emails(tmp_path, mailbox_dir):
    crashing = FakeClient(replies=[VALID_REPLY, VALID_REPLY, Crash("killed")])
    service, _, state, repo = make_service(tmp_path, mailbox_dir, crashing)
    batch = service.start("four.csv")

    with pytest.raises(Crash):
        service.run(batch.id)

    interrupted = service.get(batch.id)
    assert (interrupted.status, interrupted.active, interrupted.processed) == ("running", False, 2)
    assert state.active_batch_id is None

    restarted_client = FakeClient(replies=[VALID_REPLY, VALID_REPLY])
    restarted, _, _, _ = make_service(tmp_path, mailbox_dir, restarted_client)
    resumed = restarted.resume(batch.id)
    assert resumed.active is True
    restarted.run(batch.id)

    done = restarted.get(batch.id)
    assert (done.status, done.processed, done.ok) == ("completed", 4, 4)
    assert generate_count(restarted_client) == 2
    subjects = [call[2] for call in restarted_client.calls if call[0] == "generate"]
    assert "Subject 3" in subjects[0] and "Subject 4" in subjects[1]
    assert len(rows(repo, "SELECT * FROM decision_log")) == 4


def test_the_slot_is_released_and_the_batch_stays_resumable_when_storing_fails(tmp_path, mailbox_dir, monkeypatch):
    service, _, state, repo = make_service(tmp_path, mailbox_dir, FakeClient(replies=[VALID_REPLY] * 4))
    batch = service.start("four.csv")
    original = repo.save_result
    saved = []

    def flaky_save(email_id, response):
        if len(saved) == 2:
            raise sqlite3.OperationalError("database is locked")
        saved.append(email_id)
        original(email_id, response)

    monkeypatch.setattr(repo, "save_result", flaky_save)

    with pytest.raises(sqlite3.OperationalError):
        service.run(batch.id)

    stopped = service.get(batch.id)
    assert (stopped.status, stopped.active, stopped.processed) == ("running", False, 2)
    assert state.active_batch_id is None


def test_a_second_batch_is_refused_while_one_is_running(tmp_path, mailbox_dir):
    service, _, _, repo = make_service(tmp_path, mailbox_dir)
    first = service.start("four.csv")

    with pytest.raises(HTTPException) as error:
        service.start("four.csv")

    assert error.value.status_code == 400
    assert error.value.detail == "A batch is already running."
    assert [batch.id for batch in repo.list_batches()] == [first.id]


def test_resume_is_refused_while_a_batch_is_running(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)
    running = service.start("four.csv")

    with pytest.raises(HTTPException) as error:
        service.resume(running.id)

    assert error.value.status_code == 400


def test_start_and_resume_are_refused_while_a_benchmark_runs(tmp_path, mailbox_dir):
    service, _, state, repo = make_service(tmp_path, mailbox_dir)
    batch_id = repo.create_batch("four.csv", [])
    state.benchmark_running = True

    for call in (lambda: service.start("four.csv"), lambda: service.resume(batch_id)):
        with pytest.raises(HTTPException) as error:
            call()
        assert error.value.status_code == 400
        assert "benchmark" in error.value.detail
    assert state.active_batch_id is None


def test_a_completed_batch_cannot_be_resumed(tmp_path, mailbox_dir):
    service, _, state, _ = make_service(tmp_path, mailbox_dir, FakeClient(replies=[VALID_REPLY] * 4))
    batch = service.start("four.csv")
    service.run(batch.id)

    with pytest.raises(HTTPException) as error:
        service.resume(batch.id)

    assert error.value.status_code == 400
    assert "already completed" in error.value.detail
    assert state.active_batch_id is None


def test_an_unknown_batch_is_404(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    for call in (lambda: service.get(42), lambda: service.resume(42)):
        with pytest.raises(HTTPException) as error:
            call()
        assert error.value.status_code == 404


def test_batches_list_newest_first_and_mark_the_active_one(tmp_path, mailbox_dir):
    service, _, _, repo = make_service(tmp_path, mailbox_dir)
    older = repo.create_batch("old.csv", [])
    newer = service.start("four.csv")

    listed = service.list_batches()

    assert [batch.id for batch in listed] == [newer.id, older]
    assert [batch.active for batch in listed] == [True, False]


@pytest.mark.parametrize(
    "name",
    ["", ".", "..", "../secret.csv", "sub/four.csv", "sub\\four.csv", "/etc/passwd", "C:\\four.csv", "four.csv/", "a\x00b.csv"],
)
def test_a_name_that_is_not_a_bare_file_name_is_refused(tmp_path, mailbox_dir, name):
    (tmp_path / "secret.csv").write_text(csv_text(["hidden"]), encoding="utf-8")
    service, _, state, repo = make_service(tmp_path, mailbox_dir)

    with pytest.raises(HTTPException) as error:
        service.start(name)

    assert error.value.status_code == 400
    assert repo.list_batches() == []
    assert state.active_batch_id is None


def test_a_missing_file_a_directory_and_an_unsupported_type_are_refused(tmp_path, mailbox_dir):
    (mailbox_dir / "notes.txt").write_text("hello", encoding="utf-8")
    (mailbox_dir / "folder.csv").mkdir()
    service, _, _, repo = make_service(tmp_path, mailbox_dir)

    details = []
    for name in ("missing.csv", "folder.csv", "notes.txt"):
        with pytest.raises(HTTPException) as error:
            service.start(name)
        assert error.value.status_code == 400
        details.append(error.value.detail)

    assert details[0] == "Mailbox file not found: missing.csv"
    assert "Unsupported mailbox file type" in details[2]
    assert repo.list_batches() == []


def test_a_file_the_loader_rejects_or_with_no_emails_creates_no_batch(tmp_path, mailbox_dir):
    (mailbox_dir / "broken.csv").write_text("sender,subject\nx,y\n", encoding="utf-8")
    (mailbox_dir / "empty.csv").write_text(HEADER, encoding="utf-8")
    service, _, state, repo = make_service(tmp_path, mailbox_dir)

    with pytest.raises(HTTPException) as broken:
        service.start("broken.csv")
    with pytest.raises(HTTPException) as empty:
        service.start("empty.csv")

    assert broken.value.status_code == 400 and "missing required columns" in broken.value.detail
    assert empty.value.status_code == 400 and "no emails" in empty.value.detail
    assert repo.list_batches() == []
    assert state.active_batch_id is None


def run_together(calls):
    """Runs each call in its own thread, released at the same moment; returns each result or HTTPException."""
    barrier = threading.Barrier(len(calls))
    outcomes = [None] * len(calls)

    def worker(index, call):
        barrier.wait()
        try:
            outcomes[index] = call()
        except HTTPException as error:
            outcomes[index] = error

    threads = [threading.Thread(target=worker, args=(index, call)) for index, call in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return outcomes


def test_two_overlapping_starts_leave_one_batch_and_one_refusal(tmp_path, mailbox_dir, monkeypatch):
    service, _, state, repo = make_service(tmp_path, mailbox_dir)
    real_get_loader = batch_module.get_email_loader

    def slow_loader(path):
        loader = real_get_loader(path)
        load = loader.load

        def slow_load(file_path):
            time.sleep(0.1)  # widens the window between the idle check and the claim
            return load(file_path)

        loader.load = slow_load
        return loader

    monkeypatch.setattr(batch_module, "get_email_loader", slow_loader)

    outcomes = run_together([lambda: service.start("four.csv")] * 2)

    refused = [outcome for outcome in outcomes if isinstance(outcome, HTTPException)]
    started = [outcome for outcome in outcomes if not isinstance(outcome, HTTPException)]
    assert (len(started), len(refused)) == (1, 1)
    assert refused[0].status_code == 400
    assert [batch.id for batch in repo.list_batches()] == [started[0].id]
    assert state.active_batch_id == started[0].id


def test_two_overlapping_resumes_claim_the_batch_once(tmp_path, mailbox_dir, monkeypatch):
    service, _, state, repo = make_service(tmp_path, mailbox_dir)
    batch = service.start("four.csv")
    state.active_batch_id = None
    ensure_idle = service._ensure_idle

    def slow_ensure_idle():
        ensure_idle()
        time.sleep(0.1)  # widens the window between the idle check and the claim

    monkeypatch.setattr(service, "_ensure_idle", slow_ensure_idle)

    outcomes = run_together([lambda: service.resume(batch.id)] * 2)

    refused = [outcome for outcome in outcomes if isinstance(outcome, HTTPException)]
    assert len(refused) == 1
    assert refused[0].detail == "A batch is already running."
    assert state.active_batch_id == batch.id


def test_delete_batch_removes_the_batch_and_every_dependent_row(tmp_path, mailbox_dir):
    client = FakeClient(replies=[VALID_REPLY] * 4)
    service, _, state, repo = make_service(tmp_path, mailbox_dir, client)
    batch = service.start("four.csv")
    service.run(batch.id)
    triaged = repo.list_emails(batch.id)
    email_id = triaged[0].id
    repo.save_review_action(email_id, "approve", None)
    other = repo.create_batch("other.csv", [])

    repo.delete_batch(batch.id)

    assert [b.id for b in repo.list_batches()] == [other]
    assert repo.list_emails(batch.id) == []
    assert rows(repo, f"SELECT * FROM triage_results WHERE email_id = {email_id}") == []
    assert rows(repo, f"SELECT * FROM decision_log WHERE email_id = {email_id}") == []
    assert rows(repo, f"SELECT * FROM review_actions WHERE email_id = {email_id}") == []
    assert rows(repo, f"SELECT * FROM emails WHERE id = {email_id}") == []


def test_delete_batch_on_an_unknown_id_is_a_no_op(tmp_path, mailbox_dir):
    service, _, _, repo = make_service(tmp_path, mailbox_dir)
    kept = repo.create_batch("kept.csv", [])

    repo.delete_batch(9999)

    assert [b.id for b in repo.list_batches()] == [kept]


def test_bulk_insert_creates_a_tagged_batch_of_ten_synthetic_emails(tmp_path, mailbox_dir):
    service, _, state, repo = make_service(tmp_path, mailbox_dir)

    batch = service.bulk_insert()

    assert batch.total == 10
    assert batch.source_file.startswith("test:")
    assert batch.active is True
    assert state.active_batch_id == batch.id
    emails = repo.list_emails(batch.id)
    assert len(emails) == 10
    assert [email.subject for email in emails] == [f"Test email {n}" for n in range(1, 11)]


def test_bulk_insert_is_refused_while_a_batch_or_benchmark_is_active(tmp_path, mailbox_dir):
    service, _, state, repo = make_service(tmp_path, mailbox_dir)
    service.bulk_insert()

    with pytest.raises(HTTPException) as error:
        service.bulk_insert()
    assert error.value.status_code == 400
    assert [b.id for b in repo.list_batches()] == [1]

    state.active_batch_id = None
    state.benchmark_running = True
    with pytest.raises(HTTPException) as error:
        service.bulk_insert()
    assert error.value.status_code == 400
    assert [b.id for b in repo.list_batches()] == [1]


def test_upload_mailbox_file_stores_it_under_the_mailbox_dir_and_starts_a_batch(tmp_path, mailbox_dir):
    service, _, _, repo = make_service(tmp_path, mailbox_dir)

    uploaded = service.upload_mailbox_file("mine.csv", csv_text(["hello"]).encode("utf-8"))

    assert uploaded.file.startswith("upload-")
    assert uploaded.file.endswith(".csv")
    stored_path = mailbox_dir / uploaded.file
    assert stored_path.is_file()

    batch = service.start(uploaded.file)
    assert batch.source_file == uploaded.file
    assert batch.total == 1
    assert repo.list_batches()[0].source_file == uploaded.file


def test_upload_mailbox_file_records_it_as_pending_until_a_batch_starts(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    uploaded = service.upload_mailbox_file("mine.csv", csv_text(["hello"]).encode("utf-8"), "Week 1 inbox")

    pending = service.pending_mailbox_files()
    assert len(pending) == 1
    assert pending[0].file == uploaded.file
    assert pending[0].display_name == "Week 1 inbox"

    service.start(uploaded.file)

    assert service.pending_mailbox_files() == []


def test_upload_mailbox_file_falls_back_to_the_stored_name_with_no_display_name(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    uploaded = service.upload_mailbox_file("mine.csv", csv_text(["hello"]).encode("utf-8"))

    assert service.pending_mailbox_files()[0].display_name == uploaded.file


def test_discard_pending_mailbox_file_removes_its_record(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)
    uploaded = service.upload_mailbox_file("mine.csv", csv_text(["hello"]).encode("utf-8"))

    service.discard_pending_mailbox_file(uploaded.file)

    assert service.pending_mailbox_files() == []


def test_upload_mailbox_file_rejects_an_unsupported_extension(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    with pytest.raises(HTTPException) as error:
        service.upload_mailbox_file("notes.txt", b"not a mailbox file")
    assert error.value.status_code == 400
    assert list(mailbox_dir.iterdir()) == [mailbox_dir / "four.csv"]


def test_upload_mailbox_file_rejects_an_empty_file(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    with pytest.raises(HTTPException) as error:
        service.upload_mailbox_file("empty.csv", b"")
    assert error.value.status_code == 400


def test_upload_mailbox_file_rejects_a_file_over_the_size_cap(tmp_path, mailbox_dir, monkeypatch):
    monkeypatch.setattr(batch_module, "MAX_MAILBOX_UPLOAD_BYTES", 10)
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    with pytest.raises(HTTPException) as error:
        service.upload_mailbox_file("big.csv", b"x" * 11)
    assert error.value.status_code == 400
    assert list(mailbox_dir.iterdir()) == [mailbox_dir / "four.csv"]


def test_two_uploads_of_the_same_original_name_do_not_collide(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    first = service.upload_mailbox_file("same.csv", csv_text(["a"]).encode("utf-8"))
    second = service.upload_mailbox_file("same.csv", csv_text(["b"]).encode("utf-8"))

    assert first.file != second.file
    assert (mailbox_dir / first.file).is_file()
    assert (mailbox_dir / second.file).is_file()


def test_delete_removes_an_idle_completed_batch(tmp_path, mailbox_dir):
    client = FakeClient(replies=[VALID_REPLY] * 4)
    service, _, _, repo = make_service(tmp_path, mailbox_dir, client)
    batch = service.start("four.csv")
    service.run(batch.id)

    service.delete(batch.id)

    assert repo.list_batches() == []


def test_delete_also_removes_the_uploaded_mailbox_file(tmp_path, mailbox_dir):
    client = FakeClient(replies=[VALID_REPLY])
    service, _, _, _ = make_service(tmp_path, mailbox_dir, client)
    upload = service.upload_mailbox_file("one.csv", csv_text(["one"]).encode("utf-8"))
    batch = service.start(upload.file)
    service.run(batch.id)

    service.delete(batch.id)

    assert not (mailbox_dir / upload.file).exists()


def test_delete_of_a_bulk_insert_batch_has_no_file_to_remove(tmp_path, mailbox_dir):
    service, _, _, repo = make_service(tmp_path, mailbox_dir)
    batch = service.bulk_insert()
    service.run(batch.id)

    service.delete(batch.id)  # must not raise despite no file on disk for "test:..." sources

    assert repo.list_batches() == []


def test_delete_refuses_the_currently_active_batch(tmp_path, mailbox_dir):
    service, _, state, repo = make_service(tmp_path, mailbox_dir)
    batch = service.start("four.csv")

    with pytest.raises(HTTPException) as error:
        service.delete(batch.id)

    assert error.value.status_code == 400
    assert [b.id for b in repo.list_batches()] == [batch.id]
    assert state.active_batch_id == batch.id


def test_delete_an_unknown_batch_is_404(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    with pytest.raises(HTTPException) as error:
        service.delete(42)

    assert error.value.status_code == 404


def test_a_concurrent_resume_cannot_claim_a_batch_delete_is_removing(tmp_path, mailbox_dir, monkeypatch):
    # A crashed, un-completed batch is exactly F-17's scenario: idle (state.active_batch_id is
    # None, so delete's guard sees it as deletable) but still resumable (status stays "running").
    crashing = FakeClient(replies=[VALID_REPLY, VALID_REPLY, Crash("killed")])
    service, _, state, repo = make_service(tmp_path, mailbox_dir, crashing)
    batch = service.start("four.csv")
    with pytest.raises(Crash):
        service.run(batch.id)
    assert state.active_batch_id is None
    assert service.get(batch.id).status == "running"

    delete_started = threading.Event()
    real_delete_batch = repo.delete_batch

    def slow_delete_batch(batch_id):
        delete_started.set()
        time.sleep(0.1)  # widens the window while delete still holds batch_lock
        return real_delete_batch(batch_id)

    monkeypatch.setattr(repo, "delete_batch", slow_delete_batch)

    def delayed_resume():
        delete_started.wait(timeout=1)  # only start once delete has the lock, so it always wins the race
        return service.resume(batch.id)

    outcomes = run_together([lambda: service.delete(batch.id), delayed_resume])

    delete_outcome, resume_outcome = outcomes
    assert delete_outcome is None
    # A resume that starts once delete already holds the lock must never claim the batch's slot;
    # it blocks on batch_lock and then sees the batch already gone.
    assert isinstance(resume_outcome, HTTPException) and resume_outcome.status_code == 404
    assert repo.list_batches() == []
    assert state.active_batch_id is None


def test_stop_pauses_after_the_current_email_and_the_batch_stays_resumable(tmp_path, mailbox_dir, monkeypatch):
    client = FakeClient(replies=[VALID_REPLY, VALID_REPLY, VALID_REPLY, VALID_REPLY])
    service, _, state, repo = make_service(tmp_path, mailbox_dir, client)
    batch = service.start("four.csv")
    original_save = repo.save_result

    def stop_after_first(email_id, response):
        original_save(email_id, response)
        state.stop_batch_id = batch.id

    monkeypatch.setattr(repo, "save_result", stop_after_first)

    service.run(batch.id)

    stopped = service.get(batch.id)
    assert (stopped.status, stopped.active, stopped.processed) == ("running", False, 1)
    assert state.active_batch_id is None
    assert state.stop_batch_id is None

    monkeypatch.setattr(repo, "save_result", original_save)
    resumed = service.resume(batch.id)
    assert resumed.active is True
    service.run(batch.id)
    done = service.get(batch.id)
    assert (done.status, done.processed) == ("completed", 4)


def test_stop_is_refused_for_a_batch_that_is_not_the_active_one(tmp_path, mailbox_dir):
    service, _, state, _ = make_service(tmp_path, mailbox_dir)
    batch = service.start("four.csv")
    state.active_batch_id = None

    with pytest.raises(HTTPException) as error:
        service.stop(batch.id)
    assert error.value.status_code == 400

    with pytest.raises(HTTPException) as error:
        service.stop(999)
    assert error.value.status_code == 404


def test_run_logs_a_start_line_a_per_email_line_and_a_completion_line(tmp_path, mailbox_dir, caplog):
    service, _, _, _ = make_service(tmp_path, mailbox_dir, FakeClient(replies=[VALID_REPLY] * 4))
    batch = service.start("four.csv")

    with caplog.at_level("INFO", logger="app.services.batch"):
        service.run(batch.id)

    messages = [record.message for record in caplog.records]
    assert any("starting" in message for message in messages)
    assert sum("-> ok" in message for message in messages) == 4
    assert any("completed" in message for message in messages)


def test_run_only_triages_emails_inside_the_given_received_range(tmp_path, mailbox_dir):
    rows_text = (
        "sender,subject,body,received_at\n"
        "a@example.com,One,First,2026-01-01T00:00:00+00:00\n"
        "b@example.com,Two,Second,2026-02-01T00:00:00+00:00\n"
        "c@example.com,Three,Third,2026-03-01T00:00:00+00:00\n"
    )
    (mailbox_dir / "ranged.csv").write_text(rows_text, encoding="utf-8")
    client = FakeClient(replies=[VALID_REPLY])
    service, _, state, repo = make_service(tmp_path, mailbox_dir, client)
    batch = service.start("ranged.csv")

    service.run(
        batch.id,
        received_after=datetime(2026, 1, 15, tzinfo=timezone.utc),
        received_before=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )

    status = service.get(batch.id)
    assert status.processed == 1
    # Two emails fell outside the range and were never triaged, so the batch is not done yet.
    assert status.status == "running"
    assert status.active is False
    assert state.active_batch_id is None
    emails = repo.list_emails(batch.id)
    triaged = [email for email in emails if email.triage is not None]
    assert len(triaged) == 1
    assert triaged[0].subject == "Two"


def test_a_range_that_covers_every_email_still_completes_the_batch(tmp_path, mailbox_dir):
    client = FakeClient(replies=[VALID_REPLY] * 4)
    service, _, _, _ = make_service(tmp_path, mailbox_dir, client)
    batch = service.start("four.csv")

    service.run(batch.id, received_after=None, received_before=None)

    assert service.get(batch.id).status == "completed"


def test_a_batch_left_running_by_a_narrow_range_can_be_resumed_to_finish_the_rest(tmp_path, mailbox_dir):
    rows_text = (
        "sender,subject,body,received_at\n"
        "a@example.com,One,First,2026-01-01T00:00:00+00:00\n"
        "b@example.com,Two,Second,2026-02-01T00:00:00+00:00\n"
        "c@example.com,Three,Third,2026-03-01T00:00:00+00:00\n"
    )
    (mailbox_dir / "ranged.csv").write_text(rows_text, encoding="utf-8")
    service, _, _, repo = make_service(tmp_path, mailbox_dir, FakeClient(replies=[VALID_REPLY]))
    batch = service.start("ranged.csv")
    service.run(
        batch.id,
        received_after=datetime(2026, 1, 15, tzinfo=timezone.utc),
        received_before=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )
    assert service.get(batch.id).status == "running"

    resumed_client = FakeClient(replies=[VALID_REPLY, VALID_REPLY])
    resumed_service, _, _, _ = make_service(tmp_path, mailbox_dir, resumed_client)
    resumed_service.resume(batch.id)
    resumed_service.run(batch.id)

    done = resumed_service.get(batch.id)
    assert done.status == "completed"
    assert done.processed == 3
    triaged_subjects = {email.subject for email in repo.list_emails(batch.id) if email.triage is not None}
    assert triaged_subjects == {"One", "Two", "Three"}


def test_pending_preview_returns_timestamps_of_only_the_still_pending_emails(tmp_path, mailbox_dir):
    rows_text = (
        "sender,subject,body,received_at\n"
        "a@example.com,One,First,2026-01-01T00:00:00+00:00\n"
        "b@example.com,Two,Second,2026-02-01T00:00:00+00:00\n"
        "c@example.com,Three,Third,2026-03-01T00:00:00+00:00\n"
    )
    (mailbox_dir / "ranged.csv").write_text(rows_text, encoding="utf-8")
    service, _, _, _ = make_service(tmp_path, mailbox_dir, FakeClient(replies=[VALID_REPLY]))
    batch = service.start("ranged.csv")
    service.run(
        batch.id,
        received_after=datetime(2026, 1, 15, tzinfo=timezone.utc),
        received_before=datetime(2026, 2, 15, tzinfo=timezone.utc),
    )

    preview = service.pending_preview(batch.id)

    assert preview.received_at == [
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 3, 1, tzinfo=timezone.utc),
    ]


def test_pending_preview_rejects_an_unknown_batch(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    with pytest.raises(HTTPException) as error:
        service.pending_preview(999)

    assert error.value.status_code == 404


def test_preview_mailbox_file_returns_timestamps_without_creating_a_batch(tmp_path, mailbox_dir):
    service, _, _, repo = make_service(tmp_path, mailbox_dir)

    preview = service.preview_mailbox_file("four.csv")

    assert len(preview.received_at) == 4
    assert all(value is not None for value in preview.received_at)
    assert repo.list_batches() == []


def test_preview_mailbox_file_rejects_an_unknown_or_unsupported_file(tmp_path, mailbox_dir):
    service, _, _, _ = make_service(tmp_path, mailbox_dir)

    with pytest.raises(HTTPException) as error:
        service.preview_mailbox_file("missing.csv")
    assert error.value.status_code == 400

    (mailbox_dir / "notes.txt").write_text("not a mailbox file", encoding="utf-8")
    with pytest.raises(HTTPException) as error:
        service.preview_mailbox_file("notes.txt")
    assert error.value.status_code == 400
