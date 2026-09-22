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


def test_an_assigned_agent_can_approve_and_reject_with_no_edited_reply(service):
    (parcel,) = service.emails("chen", "deliveries")

    approved = service.review("chen", "deliveries", parcel.id, "approve", None)
    rejected = service.review("dana", "deliveries", parcel.id, "reject", None)

    assert (approved.agent_id, approved.action, approved.edited_reply) == ("chen", "approve", None)
    assert (rejected.agent_id, rejected.action, rejected.edited_reply) == ("dana", "reject", None)
    assert service.emails("chen", "deliveries")[0].review.action == "reject"


def test_an_assigned_agent_can_edit_with_a_new_reply(service):
    (parcel,) = service.emails("chen", "deliveries")

    edited = service.review("chen", "deliveries", parcel.id, "edit", "We found your parcel.")

    assert (edited.action, edited.edited_reply) == ("edit", "We found your parcel.")
    assert service.emails("chen", "deliveries")[0].review.edited_reply == "We found your parcel."


def test_reviewing_from_an_unassigned_mailbox_is_refused_with_no_row_written_and_the_denial_is_logged(service):
    (parcel,) = service.emails("chen", "deliveries")

    error = refused(lambda: service.review("asha", "deliveries", parcel.id, "approve", None))

    assert error.status_code == 403
    assert denials(service) == [{"agent_id": "asha", "mailbox": "deliveries", "reason": "not_assigned"}]


@pytest.mark.parametrize("agent_id", [None, "", "zed"])
def test_reviewing_needs_a_known_agent(service, agent_id):
    (parcel,) = service.emails("chen", "deliveries")

    error = refused(lambda: service.review(agent_id, "deliveries", parcel.id, "approve", None))

    assert error.status_code == 401


def test_reviewing_an_unknown_email_is_a_404(service):
    error = refused(lambda: service.review("chen", "deliveries", 9999, "approve", None))

    assert error.status_code == 404


def test_reviewing_an_email_through_the_wrong_mailbox_is_a_404_even_when_the_agent_is_assigned_to_both(service):
    (refund,) = service.emails("asha", "refunds")

    error = refused(lambda: service.review("asha", "support", refund.id, "approve", None))

    assert error.status_code == 404


def test_seeding_twice_does_not_duplicate_and_a_new_seed_replaces_permissions(service):
    service.seed(SEED)
    assert service.mailboxes("asha") == ["refunds", "support"]

    service.seed(Seed(agents=[Agent(id="asha", name="Asha")], assignments={"deliveries": ["asha"]}))

    assert service.mailboxes("asha") == ["deliveries"]
    assert refused(lambda: service.emails("asha", "support")).status_code == 403
    assert [email.subject for email in service.emails("asha", "deliveries")] == ["parcel one"]


def test_create_agent_succeeds_and_rejects_a_duplicate_id(service):
    created = service.create_agent("priya", "Priya")

    assert created == Agent(id="priya", name="Priya")
    assert service.agents()[-1] == Agent(id="priya", name="Priya")
    assert refused(lambda: service.create_agent("priya", "Priya Again")).status_code == 409


def test_rename_agent_succeeds_and_404s_for_an_unknown_id(service):
    renamed = service.rename_agent("ben", "Benjamin")

    assert renamed == Agent(id="ben", name="Benjamin")
    assert refused(lambda: service.rename_agent("zed", "Zed")).status_code == 404


def test_delete_agent_is_idempotent_and_clears_assignments(service):
    service.delete_agent("asha")
    service.delete_agent("asha")

    # The agent no longer exists at all, so identification itself fails (401), not the
    # assignment check (403); a lingering assignment row would still show up as 403.
    assert refused(lambda: service.emails("asha", "support")).status_code == 401


def test_list_mailboxes_returns_every_mailbox(service):
    assert service.list_mailboxes() == ["deliveries", "refunds", "support"]


def test_create_mailbox_succeeds_and_rejects_a_duplicate(service):
    created = service.create_mailbox("billing")

    assert created == "billing"
    assert service.list_mailboxes() == ["billing", "deliveries", "refunds", "support"]
    assert refused(lambda: service.create_mailbox("billing")).status_code == 409


def test_delete_mailbox_is_idempotent(service):
    service.delete_mailbox("support")
    service.delete_mailbox("support")

    assert service.list_mailboxes() == ["deliveries", "refunds"]
    assert service.mailboxes("asha") == ["refunds"]


def test_assign_and_unassign_are_idempotent(service):
    service.assign("chen", "refunds")
    service.assign("chen", "refunds")
    assert service.mailboxes("chen") == ["deliveries", "refunds", "support"]

    service.unassign("chen", "refunds")
    service.unassign("chen", "refunds")
    assert service.mailboxes("chen") == ["deliveries", "support"]
