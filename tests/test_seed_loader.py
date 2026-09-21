import json
from pathlib import Path

import pytest

from app.config import SEED_FILE
from app.loaders.seed_loader import SeedError, load_seed


def write(tmp_path, content):
    path = tmp_path / "agents.json"
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


GOOD = {
    "agents": [{"id": "asha", "name": "Asha"}, {"id": "ben", "name": "Ben"}],
    "mailboxes": {"support": ["asha", "ben"], "refunds": ["asha"]},
}


def test_a_valid_file_loads_agents_and_assignments(tmp_path):
    seed = load_seed(write(tmp_path, GOOD))

    assert [(agent.id, agent.name) for agent in seed.agents] == [("asha", "Asha"), ("ben", "Ben")]
    assert seed.assignments == {"support": ["asha", "ben"], "refunds": ["asha"]}


def test_a_bom_is_tolerated_and_repeated_ids_in_a_mailbox_are_collapsed(tmp_path):
    good = {**GOOD, "mailboxes": {"support": ["asha", "asha", "ben"]}}
    path = tmp_path / "agents.json"
    path.write_text(json.dumps(good), encoding="utf-8-sig")

    assert load_seed(path).assignments == {"support": ["asha", "ben"]}


def test_a_mailbox_nobody_is_assigned_to_is_allowed(tmp_path):
    seed = load_seed(write(tmp_path, {**GOOD, "mailboxes": {"empty": []}}))

    assert seed.assignments == {"empty": []}


@pytest.mark.parametrize(
    "content, message",
    [
        ("{not json", "not valid JSON"),
        ("[]", "needs an 'agents' list and a 'mailboxes' object"),
        ({"agents": []}, "needs an 'agents' list and a 'mailboxes' object"),
        ({"agents": {}, "mailboxes": {}}, "needs an 'agents' list and a 'mailboxes' object"),
        ({"agents": ["asha"], "mailboxes": {}}, "Agent 1 in the seed file needs"),
        ({"agents": [{"id": "asha"}], "mailboxes": {}}, "Agent 1 in the seed file needs"),
        ({"agents": [{"id": " ", "name": "Asha"}], "mailboxes": {}}, "Agent 1 in the seed file needs"),
        ({"agents": [{"id": "asha", "name": ""}], "mailboxes": {}}, "Agent 1 in the seed file needs"),
        (
            {"agents": [{"id": "asha", "name": "A"}, {"id": "asha", "name": "B"}], "mailboxes": {}},
            "'asha' appears twice",
        ),
        ({**GOOD, "mailboxes": {"support": ["asha", "zed"]}}, "unknown agent 'zed'"),
        ({**GOOD, "mailboxes": {"support": "asha"}}, "must list agent ids as strings"),
        ({**GOOD, "mailboxes": {"support": [1]}}, "must list agent ids as strings"),
        ({**GOOD, "mailboxes": {" ": ["asha"]}}, "mailbox name in the seed file is blank"),
    ],
)
def test_a_bad_file_is_rejected_with_a_clear_message(tmp_path, content, message):
    with pytest.raises(SeedError, match=message):
        load_seed(write(tmp_path, content))


def test_a_missing_file_is_rejected(tmp_path):
    with pytest.raises(SeedError, match="Seed file not found"):
        load_seed(tmp_path / "nope.json")


def test_a_directory_is_rejected_as_unreadable(tmp_path):
    with pytest.raises(SeedError, match="Could not read seed file"):
        load_seed(tmp_path)


def test_a_file_that_is_not_utf8_is_rejected(tmp_path):
    path = tmp_path / "agents.json"
    path.write_bytes(b"\xff\xfe\x00\x01")

    with pytest.raises(SeedError, match="Could not read seed file"):
        load_seed(path)


def test_the_real_seed_file_matches_the_plan():
    seed = load_seed(Path(SEED_FILE))

    assert [agent.name for agent in seed.agents] == ["Asha", "Ben", "Chen", "Dana"]
    assert seed.assignments == {
        "support": ["asha", "ben", "chen", "dana"],
        "refunds": ["asha", "ben"],
        "deliveries": ["chen", "dana"],
    }
