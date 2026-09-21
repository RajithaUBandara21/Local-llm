import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.repositories.sqlite_access import SQLiteAccessRepository
from app.repositories.sqlite_batches import SQLiteBatchRepository
from app.schemas import Agent, LoadedEmail, Seed, TriageResponse, TriageResult
from app.services.access import MAX_LOGGED_MAILBOX_CHARS, AccessService

SEED = Seed(
    agents=[Agent(id=name, name=name.title()) for name in ("asha", "ben", "chen", "dana")],
    assignments={
        "support": ["asha", "ben", "chen", "dana"],
        "refunds": ["asha", "ben"],
        "deliveries": ["chen", "dana"],
    },
)


def make_email(subject, mailbox):
    return LoadedEmail(
        sender="a@example.com", subject=subject, body_clean="body",
        received_at=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc), mailbox=mailbox,
    )


@pytest.fixture
def service(tmp_path):
    path = tmp_path / "triage.db"
    batches = SQLiteBatchRepository(path)
    access = SQLiteAccessRepository(path)
    batches.create_batch(
        "mail.csv",
        [make_email("refund one", "refunds"), make_email("parcel one", "deliveries"), make_email("hello", "support")],
    )
    result = TriageResult(
        category="delivery", priority="normal", summary="Where is it.", suggested_reply="Checking.",
        confidence=0.9, flags=[], flag_reason=None,
    )
    parcel = next(email for email in batches.pending_emails(1) if email.subject == "parcel one")
    batches.save_result(
        parcel.id, TriageResponse(status="ok", model="llama3.2", attempts=1, latency_sec=2.0, result=result)
    )
    access_service = AccessService(access, batches)
    access_service.seed(SEED)
    return access_service


def denials(service):
    connection = sqlite3.connect(service.access.path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute("SELECT agent_id, mailbox, reason FROM access_denials")]
    finally:
        connection.close()


def refused(call):
    with pytest.raises(HTTPException) as error:
        call()
    return error.value


def test_an_assigned_agent_reads_the_mailbox_with_stored_results(service):
    emails = service.emails("chen", "deliveries")

    assert [email.subject for email in emails] == ["parcel one"]
    assert emails[0].triage.status == "ok"
    assert emails[0].triage.result.category == "delivery"
    assert denials(service) == []


def test_asha_reads_support_and_refunds(service):
    assert [email.subject for email in service.emails("asha", "support")] == ["hello"]
    assert [email.subject for email in service.emails("asha", "refunds")] == ["refund one"]


def test_an_unassigned_mailbox_is_refused_with_no_data_and_the_denial_is_logged(service):
    error = refused(lambda: service.emails("asha", "deliveries"))

    assert error.status_code == 403
    assert error.detail == "You do not have access to mailbox 'deliveries'."
    assert denials(service) == [{"agent_id": "asha", "mailbox": "deliveries", "reason": "not_assigned"}]


def test_a_nonexistent_mailbox_gets_the_same_refusal_and_is_logged(service):
    unassigned = refused(lambda: service.emails("asha", "deliveries"))
    missing = refused(lambda: service.emails("asha", "nowhere"))

    assert (missing.status_code, missing.detail.replace("nowhere", "deliveries")) == (
        unassigned.status_code, unassigned.detail,
    )
    assert [row["mailbox"] for row in denials(service)] == ["deliveries", "nowhere"]


def test_a_long_mailbox_name_is_logged_only_in_part(service):
    refused(lambda: service.emails("asha", "m" * 5000))

    assert len(denials(service)[0]["mailbox"]) == MAX_LOGGED_MAILBOX_CHARS


@pytest.mark.parametrize("agent_id", [None, "", "   ", "zed", "Asha", "ASHA"])
def test_a_missing_or_unknown_agent_is_refused_and_nothing_is_logged(service, agent_id):
    for call in (lambda: service.emails(agent_id, "support"), lambda: service.mailboxes(agent_id)):
        error = refused(call)
        assert error.status_code == 401
        assert "X-Agent-Id" in error.detail
    assert denials(service) == []


def test_surrounding_whitespace_is_trimmed_but_nothing_else_is_widened(service):
    assert service.mailboxes("  asha ") == ["refunds", "support"]
    assert refused(lambda: service.mailboxes("as ha")).status_code == 401


def test_an_agent_sees_only_their_own_mailboxes(service):
    assert service.mailboxes("asha") == ["refunds", "support"]
    assert service.mailboxes("dana") == ["deliveries", "support"]


def test_the_agents_list_needs_no_identity(service):
    assert [agent.id for agent in service.agents()] == ["asha", "ben", "chen", "dana"]


def test_the_batch_filter_is_passed_through(service):
    assert service.emails("chen", "deliveries", 1)[0].batch_id == 1
    assert service.emails("chen", "deliveries", 99) == []


def test_seeding_twice_does_not_duplicate_and_a_new_seed_replaces_permissions(service):
    service.seed(SEED)
    assert service.mailboxes("asha") == ["refunds", "support"]

    service.seed(Seed(agents=[Agent(id="asha", name="Asha")], assignments={"deliveries": ["asha"]}))

    assert service.mailboxes("asha") == ["deliveries"]
    assert refused(lambda: service.emails("asha", "support")).status_code == 403
    assert [email.subject for email in service.emails("asha", "deliveries")] == ["parcel one"]
