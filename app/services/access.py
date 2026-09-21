from fastapi import HTTPException

from app.repositories.base import IAccessRepository, IBatchRepository
from app.schemas import Agent, MailboxEmail, Seed

# A mailbox name comes from the URL, so the log keeps only a bounded prefix of it.
MAX_LOGGED_MAILBOX_CHARS = 200


class AccessService:
    """Knows who the acting agent is and which mailboxes they may read."""

    def __init__(self, access: IAccessRepository, batches: IBatchRepository):
        self.access = access
        self.batches = batches

    def seed(self, seed: Seed) -> None:
        self.access.replace_directory(seed)

    def agents(self) -> list[Agent]:
        return self.access.list_agents()

    def mailboxes(self, agent_id: str | None) -> list[str]:
        return self.access.mailboxes_for(self._identify(agent_id).id)

    def emails(self, agent_id: str | None, mailbox: str, batch_id: int | None = None) -> list[MailboxEmail]:
        agent = self._identify(agent_id)
        if not self.access.is_assigned(agent.id, mailbox):
            self.access.log_denial(agent.id, mailbox[:MAX_LOGGED_MAILBOX_CHARS], "not_assigned")
            # The same answer for an unassigned and a nonexistent mailbox, so it reveals nothing about which exist.
            raise HTTPException(status_code=403, detail=f"You do not have access to mailbox '{mailbox}'.")
        return self.batches.list_mailbox_emails(mailbox, batch_id)

    def _identify(self, agent_id: str | None) -> Agent:
        agent = self.access.get_agent(agent_id.strip()) if agent_id else None
        if agent is None:
            raise HTTPException(
                status_code=401, detail="Pick an agent: send a known agent id in the X-Agent-Id header."
            )
        return agent
