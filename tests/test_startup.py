import json

import pytest

from app import dependencies, startup
from app.loaders.seed_loader import SeedError
from app.repositories.sqlite_access import SQLiteAccessRepository


def point_at(monkeypatch, tmp_path, seed_content):
    seed_file = tmp_path / "agents.json"
    if seed_content is not None:
        seed_file.write_text(json.dumps(seed_content), encoding="utf-8")
    monkeypatch.setattr(startup, "SEED_FILE", str(seed_file))
    monkeypatch.setattr(dependencies, "DATABASE_PATH", str(tmp_path / "triage.db"))
    return SQLiteAccessRepository(tmp_path / "triage.db")


def test_start_up_loads_the_seed_file_into_the_database(monkeypatch, tmp_path):
    seed = {"agents": [{"id": "asha", "name": "Asha"}], "mailboxes": {"support": ["asha"]}}
    repo = point_at(monkeypatch, tmp_path, seed)

    startup.seed_directory()
    startup.seed_directory()

    assert [agent.id for agent in repo.list_agents()] == ["asha"]
    assert repo.mailboxes_for("asha") == ["support"]


def test_a_missing_seed_file_stops_start_up_and_leaves_the_directory_alone(monkeypatch, tmp_path):
    repo = point_at(monkeypatch, tmp_path, None)

    with pytest.raises(SeedError, match="Seed file not found"):
        startup.seed_directory()

    assert repo.list_agents() == []
