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
