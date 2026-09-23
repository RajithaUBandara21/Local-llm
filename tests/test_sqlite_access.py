import sqlite3

import pytest

from app.repositories.sqlite_access import SQLiteAccessRepository
from app.schemas import Agent, Seed

SEED = Seed(
    agents=[Agent(id="asha", name="Asha"), Agent(id="ben", name="Ben"), Agent(id="chen", name="Chen")],
    assignments={"support": ["asha", "ben", "chen"], "refunds": ["asha", "ben"], "deliveries": ["chen"]},
)


@pytest.fixture
def repo(tmp_path):
    repository = SQLiteAccessRepository(tmp_path / "triage.db")
    repository.replace_directory(SEED)
    return repository


def rows(repo, sql):
    connection = sqlite3.connect(repo.path)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(sql)]
    finally:
        connection.close()


def test_agents_read_back_in_id_order(repo):
    assert [(agent.id, agent.name) for agent in repo.list_agents()] == [
        ("asha", "Asha"), ("ben", "Ben"), ("chen", "Chen"),
    ]
    assert repo.get_agent("ben") == Agent(id="ben", name="Ben")


def test_an_unknown_agent_is_none_and_the_match_is_exact(repo):
    assert repo.get_agent("zed") is None
    assert repo.get_agent("Asha") is None
    assert repo.get_agent("asha ") is None
    assert repo.get_agent("") is None


def test_mailboxes_for_an_agent_are_sorted(repo):
    assert repo.mailboxes_for("asha") == ["refunds", "support"]
    assert repo.mailboxes_for("chen") == ["deliveries", "support"]
    assert repo.mailboxes_for("zed") == []


def test_assignment_checks_are_exact(repo):
    assert repo.is_assigned("asha", "support") is True
    assert repo.is_assigned("asha", "deliveries") is False
    assert repo.is_assigned("asha", "Support") is False
    assert repo.is_assigned("asha", "nowhere") is False
    assert repo.is_assigned("zed", "support") is False


def test_replacing_the_directory_twice_does_not_duplicate(repo):
    repo.replace_directory(SEED)

    assert len(repo.list_agents()) == 3
    assert len(rows(repo, "SELECT * FROM mailbox_assignments")) == 6


def test_replacing_with_different_data_leaves_only_the_new_data(repo):
    repo.replace_directory(Seed(agents=[Agent(id="dana", name="Dana")], assignments={"deliveries": ["dana"]}))

    assert [agent.id for agent in repo.list_agents()] == ["dana"]
    assert repo.mailboxes_for("asha") == []
    assert repo.mailboxes_for("dana") == ["deliveries"]


def test_a_failed_replacement_keeps_the_old_directory(repo):
    broken = Seed(agents=[Agent(id="dana", name="Dana")], assignments={"deliveries": ["nobody"]})

    with pytest.raises(sqlite3.IntegrityError):
        repo.replace_directory(broken)

    assert [agent.id for agent in repo.list_agents()] == ["asha", "ben", "chen"]
    assert repo.is_assigned("asha", "support") is True


def test_a_denial_is_stored_with_the_agent_mailbox_reason_and_time(repo):
    repo.log_denial("asha", "deliveries", "not_assigned")

    (row,) = rows(repo, "SELECT agent_id, mailbox, reason, created_at FROM access_denials")
    assert (row["agent_id"], row["mailbox"], row["reason"]) == ("asha", "deliveries", "not_assigned")
    assert row["created_at"].endswith("+00:00")


def test_denials_survive_replacing_the_directory(repo):
    repo.log_denial("asha", "deliveries", "not_assigned")

    repo.replace_directory(Seed(agents=[Agent(id="dana", name="Dana")], assignments={}))

    assert len(rows(repo, "SELECT * FROM access_denials")) == 1


def test_values_are_bound_not_formatted_into_sql(repo):
    repo.log_denial("x'); DROP TABLE agents; --", "y", "not_assigned")

    assert repo.get_agent("x'); DROP TABLE agents; --") is None
    assert len(repo.list_agents()) == 3
    assert rows(repo, "SELECT agent_id FROM access_denials")[0]["agent_id"] == "x'); DROP TABLE agents; --"


def test_replace_directory_seeds_the_mailboxes_table_from_assignment_keys(repo):
    assert repo.list_mailboxes() == ["deliveries", "refunds", "support"]

    repo.replace_directory(Seed(agents=[Agent(id="dana", name="Dana")], assignments={"deliveries": ["dana"]}))

    assert repo.list_mailboxes() == ["deliveries"]


def test_create_mailbox_adds_a_new_one_and_rejects_a_duplicate(repo):
    repo.create_mailbox("billing")

    assert repo.list_mailboxes() == ["billing", "deliveries", "refunds", "support"]
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_mailbox("billing")


def test_delete_mailbox_removes_it_and_its_assignments_leaving_others_untouched(repo):
    repo.delete_mailbox("support")

    assert repo.list_mailboxes() == ["deliveries", "refunds"]
    assert rows(repo, "SELECT * FROM mailbox_assignments WHERE mailbox = 'support'") == []
    assert repo.mailboxes_for("asha") == ["refunds"]


def test_delete_mailbox_on_an_unknown_name_is_a_no_op(repo):
    repo.delete_mailbox("not-a-mailbox")

    assert repo.list_mailboxes() == ["deliveries", "refunds", "support"]


def test_create_agent_adds_a_new_one_and_rejects_a_duplicate_id(repo):
    repo.create_agent(Agent(id="dana", name="Dana"))

    assert repo.get_agent("dana") == Agent(id="dana", name="Dana")
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_agent(Agent(id="dana", name="Dana Again"))


def test_rename_agent_updates_the_name_and_raises_for_an_unknown_id(repo):
    renamed = repo.rename_agent("ben", "Benjamin")

    assert renamed == Agent(id="ben", name="Benjamin")
    assert repo.get_agent("ben") == Agent(id="ben", name="Benjamin")
    with pytest.raises(KeyError):
        repo.rename_agent("zed", "Zed")


def test_delete_agent_removes_it_and_its_assignments_leaving_others_untouched(repo):
    repo.delete_agent("asha")

    assert repo.get_agent("asha") is None
    assert rows(repo, "SELECT * FROM mailbox_assignments WHERE agent_id = 'asha'") == []
    assert repo.mailboxes_for("ben") == ["refunds", "support"]


def test_delete_agent_on_an_unknown_id_is_a_no_op(repo):
    repo.delete_agent("zed")

    assert [agent.id for agent in repo.list_agents()] == ["asha", "ben", "chen"]


def test_assign_is_idempotent_and_readable_through_existing_methods(repo):
    repo.assign("chen", "refunds")
    repo.assign("chen", "refunds")

    assert repo.mailboxes_for("chen") == ["deliveries", "refunds", "support"]
    assert repo.is_assigned("chen", "refunds") is True
    assert len(rows(repo, "SELECT * FROM mailbox_assignments WHERE agent_id = 'chen' AND mailbox = 'refunds'")) == 1


def test_unassign_removes_the_row_and_is_a_no_op_when_absent(repo):
    repo.unassign("asha", "support")
    repo.unassign("asha", "support")

    assert repo.mailboxes_for("asha") == ["refunds"]
    assert repo.is_assigned("asha", "support") is False


def test_assign_is_a_safe_no_op_for_a_nonexistent_agent_or_mailbox(repo):
    # F-17: assigning a real mailbox to an unknown agent (or vice versa) must never raise
    # (the FK on mailbox_assignments.agent_id would otherwise surface as an unhandled 500) and
    # must never create a phantom row for a mailbox that does not exist in the mailboxes table.
    repo.assign("ghost-agent", "support")
    repo.assign("asha", "ghost-mailbox")

    assert rows(repo, "SELECT * FROM mailbox_assignments WHERE agent_id = 'ghost-agent'") == []
    assert rows(repo, "SELECT * FROM mailbox_assignments WHERE mailbox = 'ghost-mailbox'") == []
    assert repo.list_mailboxes() == ["deliveries", "refunds", "support"]


def test_get_gmail_connection_is_none_before_any_save(repo):
    assert repo.get_gmail_connection() is None


def test_save_gmail_connection_makes_it_readable(repo):
    repo.save_gmail_connection("support", "agent@example.com", b"encrypted-token")

    connection = repo.get_gmail_connection()
    assert connection is not None
    assert connection.mailbox == "support"
    assert connection.email == "agent@example.com"
    assert connection.connected_at is not None


def test_save_gmail_connection_replaces_rather_than_duplicates(repo):
    repo.save_gmail_connection("support", "first@example.com", b"first-token")
    repo.save_gmail_connection("refunds", "second@example.com", b"second-token")

    assert rows(repo, "SELECT * FROM gmail_connection") == rows(
        repo, "SELECT * FROM gmail_connection WHERE mailbox = 'refunds'"
    )
    connection = repo.get_gmail_connection()
    assert connection.mailbox == "refunds"
    assert connection.email == "second@example.com"


def test_delete_gmail_connection_removes_it_and_is_a_no_op_when_absent(repo):
    repo.save_gmail_connection("support", "agent@example.com", b"encrypted-token")

    repo.delete_gmail_connection()
    assert repo.get_gmail_connection() is None

    repo.delete_gmail_connection()
    assert repo.get_gmail_connection() is None
