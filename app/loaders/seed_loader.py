import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas import Agent, Seed


class SeedError(Exception):
    """The seed file is missing or wrong; the message says what to fix."""


def load_seed(path: Path) -> Seed:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise SeedError(f"Seed file not found: {path}") from None
    except (OSError, UnicodeDecodeError) as error:
        raise SeedError(f"Could not read seed file {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise SeedError(f"Seed file {path} is not valid JSON: {error}") from error

    if not isinstance(raw, dict) or not isinstance(raw.get("agents"), list) or not isinstance(raw.get("mailboxes"), dict):
        raise SeedError(f"Seed file {path} needs an 'agents' list and a 'mailboxes' object.")

    agents = _read_agents(raw["agents"])
    known = {agent.id for agent in agents}
    assignments: dict[str, list[str]] = {}
    for mailbox, agent_ids in raw["mailboxes"].items():
        if not mailbox.strip():
            raise SeedError("A mailbox name in the seed file is blank.")
        if not isinstance(agent_ids, list) or not all(isinstance(agent_id, str) for agent_id in agent_ids):
            raise SeedError(f"Mailbox {mailbox!r} must list agent ids as strings.")
        unknown = [agent_id for agent_id in agent_ids if agent_id not in known]
        if unknown:
            raise SeedError(f"Mailbox {mailbox!r} is assigned to unknown agent {unknown[0]!r}.")
        assignments[mailbox] = list(dict.fromkeys(agent_ids))
    return Seed(agents=agents, assignments=assignments)


def _read_agents(entries: list) -> list[Agent]:
    agents: list[Agent] = []
    for number, entry in enumerate(entries, start=1):
        try:
            agent = Agent.model_validate(entry)
        except ValidationError:
            raise SeedError(f"Agent {number} in the seed file needs a non-blank 'id' and 'name'.") from None
        if any(agent.id == other.id for other in agents):
            raise SeedError(f"Agent id {agent.id!r} appears twice in the seed file.")
        agents.append(agent)
    return agents
