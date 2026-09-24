import asyncio
import io
import json
from datetime import datetime, timezone

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.repositories.base import IMetricsRepository
from app.repositories.sqlite_batches import SQLiteBatchRepository
from app.routes.benchmark import (
    get_benchmark_config_endpoint,
    get_benchmark_status_endpoint,
    get_dashboard_metrics_endpoint,
    start_benchmark_endpoint,
)
from app.routes.batches import (
    bulk_insert_endpoint,
    create_batch_endpoint,
    delete_batch_endpoint,
    discard_pending_mailbox_file_endpoint,
    get_batch_endpoint,
    list_batches_endpoint,
    list_emails_endpoint,
    list_pending_mailbox_files_endpoint,
    preview_mailbox_file_endpoint,
    resume_batch_endpoint,
    review_email_endpoint,
    stop_batch_endpoint,
    upload_mailbox_file_endpoint,
)
from app.routes.health import health_check
from app.routes.triage import triage_endpoint
from app.schemas import (
    BatchRequest, BenchmarkRequest, BenchmarkSetting, ResumeBatchRequest, ReviewActionRequest, TriageRequest,
)
from app.services.batch import BatchService
from app.services.benchmark import BenchmarkService
from app.services.triage import TriageService
from app.state import AppState
from tests.fakes import FakeClient


class FakeRepository(IMetricsRepository):
    def __init__(self, error=None):
        self.error = error

    def get_latest_metrics(self):
        if self.error:
            raise self.error
        return {"latest_benchmark_file": "run.csv", "total_runs": 0, "data": []}


def test_health_reports_the_service():
    assert health_check() == {"status": "healthy", "service": "Local AI Assistant API"}


def test_config_returns_the_models_and_temperatures():
    from app.config import MAX_RUNS_PER_PROMPT, MODELS, RUNS_PER_PROMPT, TEMPERATURES

    assert get_benchmark_config_endpoint() == {
        "models": MODELS,
        "temperatures": TEMPERATURES,
        "default_runs_per_prompt": RUNS_PER_PROMPT,
        "max_runs_per_prompt": MAX_RUNS_PER_PROMPT,
    }


def test_start_schedules_the_pipeline_in_the_background():
    state = AppState()
    service = BenchmarkService(state, FakeClient())
    tasks = BackgroundTasks()

    result = start_benchmark_endpoint(tasks, state, service)

    assert result == {"status": "Benchmark initiated in the background."}
    assert [task.func for task in tasks.tasks] == [service.run_pipeline]
    assert tasks.tasks[0].args == (service.build_plan(None),)


def test_start_passes_the_chosen_settings_to_the_pipeline():
    state = AppState()
    service = BenchmarkService(state, FakeClient())
    tasks = BackgroundTasks()
    request = BenchmarkRequest(
        runs_per_prompt=1, configs=[BenchmarkSetting(model="llama3.2", temperature=0.7)]
    )

    start_benchmark_endpoint(tasks, state, service, request)

    (plan,) = tasks.tasks[0].args
    assert plan.runs_per_prompt == 1
    assert plan.jobs == [("llama3.2", [0.7])]


def test_start_refuses_a_bad_request_and_schedules_nothing():
    state = AppState()
    service = BenchmarkService(state, FakeClient())
    tasks = BackgroundTasks()
    request = BenchmarkRequest(configs=[BenchmarkSetting(model="gpt-9", temperature=0.0)])

    with pytest.raises(HTTPException) as error:
        start_benchmark_endpoint(tasks, state, service, request)

    assert error.value.status_code == 400
    assert tasks.tasks == []


def test_start_is_refused_while_a_benchmark_is_running():
    state = AppState()
    state.benchmark_running = True
    tasks = BackgroundTasks()
    service = BenchmarkService(state, FakeClient())

    with pytest.raises(HTTPException) as error:
        start_benchmark_endpoint(tasks, state, service)

    assert error.value.status_code == 400
    assert error.value.detail == "A benchmark is already running."
    assert tasks.tasks == []


@pytest.mark.parametrize("running", [False, True])
def test_status_reflects_the_running_flag(running):
    state = AppState()
    state.benchmark_running = running

    assert get_benchmark_status_endpoint(state) == {"benchmark_running": running}


def test_metrics_returns_the_repository_result():
    assert get_dashboard_metrics_endpoint(FakeRepository())["latest_benchmark_file"] == "run.csv"


def test_missing_results_map_to_404():
    repo = FakeRepository(FileNotFoundError("No benchmark CSV files found."))

    with pytest.raises(HTTPException) as error:
        get_dashboard_metrics_endpoint(repo)

    assert error.value.status_code == 404
    assert error.value.detail == "No benchmark CSV files found."


def test_triage_returns_the_service_result_as_a_response():
    reply = json.dumps({
        "category": "spam", "priority": "low", "summary": "Unsolicited offer.",
        "suggested_reply": "No reply needed.", "confidence": 0.95,
    })
    service = TriageService(FakeClient(replies=[reply]), AppState())

    response = triage_endpoint(TriageRequest(body="Buy now!"), service)

    assert response.status == "ok"
    assert response.result.category == "spam"
    assert response.result.flags == []


def test_triage_surfaces_the_benchmark_refusal():
    state = AppState()
    state.benchmark_running = True
    service = TriageService(FakeClient(), state)

    with pytest.raises(HTTPException) as error:
        triage_endpoint(TriageRequest(body="hello"), service)

    assert error.value.status_code == 400


def make_batch_service(tmp_path, state=None):
    state = state or AppState()
    mailbox = tmp_path / "mail"
    mailbox.mkdir(exist_ok=True)
    (mailbox / "two.csv").write_text(
        "sender,subject,body,received_at\n"
        "a@example.com,One,First,2026-03-02T08:00:00+00:00\n"
        "b@example.com,Two,Second,2026-03-02T08:01:00+00:00\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "triage.db"
    repository = SQLiteBatchRepository(db_path)
    return BatchService(repository, TriageService(FakeClient(), state), state, mailbox), state


def test_creating_a_batch_schedules_its_worker_and_returns_the_status(tmp_path):
    service, state = make_batch_service(tmp_path)
    tasks = BackgroundTasks()

    batch = create_batch_endpoint(BatchRequest(file="two.csv"), tasks, service)

    assert (batch.status, batch.total, batch.active) == ("running", 2, True)
    assert [task.func for task in tasks.tasks] == [service.run]
    assert tasks.tasks[0].args == (batch.id, None, None)
    assert state.active_batch_id == batch.id


def test_creating_a_batch_forwards_the_received_range_to_its_worker(tmp_path):
    service, _ = make_batch_service(tmp_path)
    tasks = BackgroundTasks()
    after = datetime(2026, 1, 1, tzinfo=timezone.utc)
    before = datetime(2026, 2, 1, tzinfo=timezone.utc)

    batch = create_batch_endpoint(
        BatchRequest(file="two.csv", received_after=after, received_before=before), tasks, service
    )

    assert tasks.tasks[0].args == (batch.id, after, before)


def test_a_refused_batch_schedules_nothing(tmp_path):
    service, _ = make_batch_service(tmp_path)
    tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as error:
        create_batch_endpoint(BatchRequest(file="../two.csv"), tasks, service)

    assert error.value.status_code == 400
    assert tasks.tasks == []


def test_batches_can_be_read_one_at_a_time_and_as_a_list(tmp_path):
    service, _ = make_batch_service(tmp_path)
    batch = create_batch_endpoint(BatchRequest(file="two.csv"), BackgroundTasks(), service)

    assert get_batch_endpoint(batch.id, service).id == batch.id
    assert [item.id for item in list_batches_endpoint(service=service)] == [batch.id]
    assert list_batches_endpoint(limit=1, offset=1, service=service) == []

    with pytest.raises(HTTPException) as error:
        get_batch_endpoint(999, service)
    assert error.value.status_code == 404


def test_resuming_schedules_the_worker_and_unknown_or_busy_batches_are_refused(tmp_path):
    service, state = make_batch_service(tmp_path)
    first = create_batch_endpoint(BatchRequest(file="two.csv"), BackgroundTasks(), service)
    state.active_batch_id = None
    tasks = BackgroundTasks()

    resumed = resume_batch_endpoint(first.id, ResumeBatchRequest(), tasks, service)

    assert resumed.active is True
    assert tasks.tasks[0].args == (first.id, None, None)
    with pytest.raises(HTTPException) as busy:
        resume_batch_endpoint(first.id, ResumeBatchRequest(), BackgroundTasks(), service)
    assert busy.value.status_code == 400
    with pytest.raises(HTTPException) as missing:
        resume_batch_endpoint(999, ResumeBatchRequest(), BackgroundTasks(), service)
    assert missing.value.status_code == 404


def test_stop_endpoint_flags_the_active_batch_and_refuses_an_inactive_one(tmp_path):
    service, state = make_batch_service(tmp_path)
    batch = create_batch_endpoint(BatchRequest(file="two.csv"), BackgroundTasks(), service)

    stopped = stop_batch_endpoint(batch.id, service)

    assert stopped.id == batch.id
    assert state.stop_batch_id == batch.id

    state.active_batch_id = None
    with pytest.raises(HTTPException) as error:
        stop_batch_endpoint(batch.id, service)
    assert error.value.status_code == 400

    with pytest.raises(HTTPException) as missing:
        stop_batch_endpoint(999, service)
    assert missing.value.status_code == 404


def test_bulk_insert_schedules_its_worker_and_returns_the_status(tmp_path):
    service, state = make_batch_service(tmp_path)
    tasks = BackgroundTasks()

    batch = bulk_insert_endpoint(tasks, service)

    assert (batch.total, batch.active) == (10, True)
    assert batch.source_file.startswith("test:")
    assert [task.func for task in tasks.tasks] == [service.run]
    assert tasks.tasks[0].args == (batch.id,)
    assert state.active_batch_id == batch.id


def test_upload_mailbox_file_endpoint_stores_it_and_returns_its_name(tmp_path):
    service, _ = make_batch_service(tmp_path)
    upload = UploadFile(io.BytesIO(b"sender,subject,body,received_at\n"), filename="mine.csv")

    result = asyncio.run(upload_mailbox_file_endpoint(upload, name=None, service=service))

    assert result.file.startswith("upload-")
    assert result.file.endswith(".csv")


def test_pending_mailbox_files_endpoint_lists_and_discards(tmp_path):
    service, _ = make_batch_service(tmp_path)
    upload = UploadFile(io.BytesIO(b"sender,subject,body,received_at\n"), filename="mine.csv")
    uploaded = asyncio.run(upload_mailbox_file_endpoint(upload, name="My inbox", service=service))

    pending = list_pending_mailbox_files_endpoint(service=service)
    assert [p.file for p in pending] == [uploaded.file]
    assert pending[0].display_name == "My inbox"

    assert discard_pending_mailbox_file_endpoint(uploaded.file, service=service) is None
    assert list_pending_mailbox_files_endpoint(service=service) == []


def test_preview_mailbox_file_endpoint_returns_timestamps_and_creates_no_batch(tmp_path):
    service, _ = make_batch_service(tmp_path)

    preview = preview_mailbox_file_endpoint("two.csv", service)

    assert len(preview.received_at) == 2
    assert list_batches_endpoint(service=service) == []

    with pytest.raises(HTTPException) as error:
        preview_mailbox_file_endpoint("missing.csv", service)
    assert error.value.status_code == 400


def test_delete_batch_endpoint_removes_it_and_propagates_service_errors(tmp_path):
    service, state = make_batch_service(tmp_path)
    batch = create_batch_endpoint(BatchRequest(file="two.csv"), BackgroundTasks(), service)

    with pytest.raises(HTTPException) as active:
        delete_batch_endpoint(batch.id, service)
    assert active.value.status_code == 400

    state.active_batch_id = None
    assert delete_batch_endpoint(batch.id, service) is None
    assert list_batches_endpoint(service=service) == []

    with pytest.raises(HTTPException) as missing:
        delete_batch_endpoint(999, service)
    assert missing.value.status_code == 404


def test_a_benchmark_cannot_start_while_a_batch_is_running():
    state = AppState()
    state.active_batch_id = 3
    tasks = BackgroundTasks()
    service = BenchmarkService(state, FakeClient())

    with pytest.raises(HTTPException) as error:
        start_benchmark_endpoint(tasks, state, service)

    assert error.value.status_code == 400
    assert "batch" in error.value.detail
    assert tasks.tasks == []


def test_list_emails_endpoint_returns_every_stored_email(tmp_path):
    service, _ = make_batch_service(tmp_path)
    batch = create_batch_endpoint(BatchRequest(file="two.csv"), BackgroundTasks(), service)

    emails = list_emails_endpoint(None, service=service)

    assert [email.subject for email in emails] == ["One", "Two"]
    assert emails[0].triage is None
    assert list_emails_endpoint(batch.id, service=service) == emails
    assert [e.subject for e in list_emails_endpoint(None, limit=1, service=service)] == ["One"]
    assert [e.subject for e in list_emails_endpoint(None, limit=1, offset=1, service=service)] == ["Two"]


def test_a_review_action_is_passed_through_and_returned(tmp_path):
    service, _ = make_batch_service(tmp_path)
    create_batch_endpoint(BatchRequest(file="two.csv"), BackgroundTasks(), service)
    (first, _) = list_emails_endpoint(None, service=service)

    review = review_email_endpoint(first.id, ReviewActionRequest(action="approve"), service)

    assert (review.email_id, review.action) == (first.id, "approve")


def test_a_review_action_on_an_unknown_email_is_404(tmp_path):
    service, _ = make_batch_service(tmp_path)

    with pytest.raises(HTTPException) as missing:
        review_email_endpoint(999, ReviewActionRequest(action="approve"), service)

    assert missing.value.status_code == 404
