import json

import pytest
from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError

from app.repositories.base import IMetricsRepository
from app.repositories.sqlite_access import SQLiteAccessRepository
from app.repositories.sqlite_batches import SQLiteBatchRepository
from app.routes.benchmark import (
    get_benchmark_config_endpoint,
    get_benchmark_status_endpoint,
    get_dashboard_metrics_endpoint,
    start_benchmark_endpoint,
)
from app.routes.access import (
    assign_mailbox_endpoint,
    create_agent_endpoint,
    create_mailbox_endpoint,
    delete_agent_endpoint,
    delete_mailbox_endpoint,
    list_agents_endpoint,
    list_all_mailboxes_endpoint,
    list_mailbox_emails_endpoint,
    list_mailboxes_endpoint,
    rename_agent_endpoint,
    review_email_endpoint,
    unassign_mailbox_endpoint,
)
from app.routes.batches import (
    bulk_insert_endpoint,
    create_batch_endpoint,
    delete_batch_endpoint,
    get_batch_endpoint,
    list_batches_endpoint,
    resume_batch_endpoint,
)
from app.routes.health import health_check
from app.routes.triage import triage_endpoint
from app.schemas import (
    Agent, AgentRenameRequest, BatchRequest, BenchmarkRequest, BenchmarkSetting, LoadedEmail, MailboxCreateRequest,
    ReviewActionRequest, Seed, TriageRequest,
)
from app.services.access import AccessService
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
        "sender,subject,body,received_at,mailbox\n"
        "a@example.com,One,First,2026-03-02T08:00:00+00:00,support\n"
        "b@example.com,Two,Second,2026-03-02T08:01:00+00:00,support\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "triage.db"
    repository = SQLiteBatchRepository(db_path)
    access = SQLiteAccessRepository(db_path)
    access.replace_directory(Seed(agents=[Agent(id="chen", name="Chen")], assignments={"support": ["chen"]}))
    return BatchService(repository, TriageService(FakeClient(), state), state, mailbox, access), state


def test_creating_a_batch_schedules_its_worker_and_returns_the_status(tmp_path):
    service, state = make_batch_service(tmp_path)
    tasks = BackgroundTasks()

    batch = create_batch_endpoint(BatchRequest(file="two.csv"), tasks, service)

    assert (batch.status, batch.total, batch.active) == ("running", 2, True)
    assert [task.func for task in tasks.tasks] == [service.run]
    assert tasks.tasks[0].args == (batch.id,)
    assert state.active_batch_id == batch.id


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
    assert [item.id for item in list_batches_endpoint(service)] == [batch.id]

    with pytest.raises(HTTPException) as error:
        get_batch_endpoint(999, service)
    assert error.value.status_code == 404


def test_resuming_schedules_the_worker_and_unknown_or_busy_batches_are_refused(tmp_path):
    service, state = make_batch_service(tmp_path)
    first = create_batch_endpoint(BatchRequest(file="two.csv"), BackgroundTasks(), service)
    state.active_batch_id = None
    tasks = BackgroundTasks()

    resumed = resume_batch_endpoint(first.id, tasks, service)

    assert resumed.active is True
    assert tasks.tasks[0].args == (first.id,)
    with pytest.raises(HTTPException) as busy:
        resume_batch_endpoint(first.id, BackgroundTasks(), service)
    assert busy.value.status_code == 400
    with pytest.raises(HTTPException) as missing:
        resume_batch_endpoint(999, BackgroundTasks(), service)
    assert missing.value.status_code == 404


def test_bulk_insert_schedules_its_worker_and_returns_the_status(tmp_path):
    service, state = make_batch_service(tmp_path)
    tasks = BackgroundTasks()

    batch = bulk_insert_endpoint("support", tasks, service)

    assert (batch.total, batch.active) == (10, True)
    assert batch.source_file.startswith("test:support:")
    assert [task.func for task in tasks.tasks] == [service.run]
    assert tasks.tasks[0].args == (batch.id,)
    assert state.active_batch_id == batch.id


def test_bulk_insert_refuses_an_unknown_mailbox_and_schedules_nothing(tmp_path):
    service, _ = make_batch_service(tmp_path)
    tasks = BackgroundTasks()

    with pytest.raises(HTTPException) as error:
        bulk_insert_endpoint("not-a-real-mailbox", tasks, service)

    assert error.value.status_code == 400
    assert tasks.tasks == []


def test_delete_batch_endpoint_removes_it_and_propagates_service_errors(tmp_path):
    service, state = make_batch_service(tmp_path)
    batch = create_batch_endpoint(BatchRequest(file="two.csv"), BackgroundTasks(), service)

    with pytest.raises(HTTPException) as active:
        delete_batch_endpoint(batch.id, service)
    assert active.value.status_code == 400

    state.active_batch_id = None
    assert delete_batch_endpoint(batch.id, service) is None
    assert list_batches_endpoint(service) == []

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


def make_access_service(tmp_path):
    path = tmp_path / "triage.db"
    batches = SQLiteBatchRepository(path)
    access = AccessService(SQLiteAccessRepository(path), batches)
    access.seed(Seed(
        agents=[Agent(id="asha", name="Asha"), Agent(id="chen", name="Chen")],
        assignments={"support": ["asha", "chen"], "deliveries": ["chen"]},
    ))
    batches.create_batch("mail.csv", [LoadedEmail(
        sender="a@example.com", subject="Parcel", body_clean="Where is it?", received_at=None, mailbox="deliveries",
    )])
    return access


def test_the_agent_list_needs_no_identity(tmp_path):
    assert [agent.id for agent in list_agents_endpoint(make_access_service(tmp_path))] == ["asha", "chen"]


def test_an_agent_header_is_passed_through_to_the_mailbox_list(tmp_path):
    service = make_access_service(tmp_path)

    assert list_mailboxes_endpoint("asha", service) == ["support"]
    assert list_mailboxes_endpoint("chen", service) == ["deliveries", "support"]


def test_a_mailbox_read_returns_the_emails_for_an_assigned_agent(tmp_path):
    service = make_access_service(tmp_path)

    emails = list_mailbox_emails_endpoint("deliveries", None, "chen", service)

    assert [email.subject for email in emails] == ["Parcel"]
    assert emails[0].triage is None


def test_a_mailbox_read_is_refused_for_an_unassigned_agent_and_without_an_identity(tmp_path):
    service = make_access_service(tmp_path)

    with pytest.raises(HTTPException) as denied:
        list_mailbox_emails_endpoint("deliveries", None, "asha", service)
    with pytest.raises(HTTPException) as anonymous:
        list_mailbox_emails_endpoint("deliveries", None, None, service)
    with pytest.raises(HTTPException) as unknown:
        list_mailboxes_endpoint("zed", service)

    assert (denied.value.status_code, anonymous.value.status_code, unknown.value.status_code) == (403, 401, 401)


def test_a_review_action_is_passed_through_and_returned(tmp_path):
    service = make_access_service(tmp_path)
    (parcel,) = list_mailbox_emails_endpoint("deliveries", None, "chen", service)

    review = review_email_endpoint(
        "deliveries", parcel.id, ReviewActionRequest(action="approve"), "chen", service
    )

    assert (review.email_id, review.agent_id, review.action) == (parcel.id, "chen", "approve")


def test_a_review_action_from_an_unassigned_agent_is_refused(tmp_path):
    service = make_access_service(tmp_path)
    (parcel,) = list_mailbox_emails_endpoint("deliveries", None, "chen", service)

    with pytest.raises(HTTPException) as denied:
        review_email_endpoint("deliveries", parcel.id, ReviewActionRequest(action="approve"), "asha", service)

    assert denied.value.status_code == 403


def test_create_agent_endpoint_returns_the_created_agent_and_rejects_a_duplicate(tmp_path):
    service = make_access_service(tmp_path)

    created = create_agent_endpoint(Agent(id="priya", name="Priya"), service)

    assert created == Agent(id="priya", name="Priya")
    with pytest.raises(HTTPException) as duplicate:
        create_agent_endpoint(Agent(id="priya", name="Priya"), service)
    assert duplicate.value.status_code == 409


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_agent_or_mailbox_names_are_rejected_by_request_validation_before_the_handler_runs(blank):
    # NonBlankText on the request body models is the actual HTTP-reachable guard (a 422 from
    # FastAPI's request validation); the service layer never sees a blank value to check itself.
    with pytest.raises(ValidationError):
        Agent(id=blank, name="Name")
    with pytest.raises(ValidationError):
        Agent(id="id", name=blank)
    with pytest.raises(ValidationError):
        AgentRenameRequest(name=blank)
    with pytest.raises(ValidationError):
        MailboxCreateRequest(name=blank)


def test_rename_agent_endpoint_returns_the_updated_agent_and_404s_unknown(tmp_path):
    service = make_access_service(tmp_path)

    renamed = rename_agent_endpoint("chen", AgentRenameRequest(name="Chen Wu"), service)

    assert renamed == Agent(id="chen", name="Chen Wu")
    with pytest.raises(HTTPException) as missing:
        rename_agent_endpoint("zed", AgentRenameRequest(name="Zed"), service)
    assert missing.value.status_code == 404


def test_delete_agent_endpoint_is_idempotent(tmp_path):
    service = make_access_service(tmp_path)

    assert delete_agent_endpoint("chen", service) is None
    assert delete_agent_endpoint("chen", service) is None
    assert "chen" not in [agent.id for agent in list_agents_endpoint(service)]


def test_admin_mailbox_endpoints_list_create_and_delete(tmp_path):
    service = make_access_service(tmp_path)

    assert list_all_mailboxes_endpoint(service) == ["deliveries", "support"]

    created = create_mailbox_endpoint(MailboxCreateRequest(name="billing"), service)
    assert created == {"name": "billing"}
    assert list_all_mailboxes_endpoint(service) == ["billing", "deliveries", "support"]

    with pytest.raises(HTTPException) as duplicate:
        create_mailbox_endpoint(MailboxCreateRequest(name="billing"), service)
    assert duplicate.value.status_code == 409

    assert delete_mailbox_endpoint("billing", service) is None
    assert list_all_mailboxes_endpoint(service) == ["deliveries", "support"]


def test_assign_and_unassign_mailbox_endpoints_are_idempotent(tmp_path):
    service = make_access_service(tmp_path)

    assert assign_mailbox_endpoint("support", "chen", service) is None
    assert assign_mailbox_endpoint("support", "chen", service) is None
    assert list_mailboxes_endpoint("chen", service) == ["deliveries", "support"]

    assert unassign_mailbox_endpoint("support", "chen", service) is None
    assert unassign_mailbox_endpoint("support", "chen", service) is None
    assert list_mailboxes_endpoint("chen", service) == ["deliveries"]
