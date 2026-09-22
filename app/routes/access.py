from fastapi import APIRouter, Depends, Header, Response, status

from app.dependencies import get_access_service
from app.schemas import Agent, AgentRenameRequest, MailboxCreateRequest, MailboxEmail, ReviewAction, ReviewActionRequest
from app.services.access import AccessService

router = APIRouter()


@router.get("/api/agents", response_model=list[Agent])
def list_agents_endpoint(service: AccessService = Depends(get_access_service)):
    return service.agents()


@router.get("/api/mailboxes", response_model=list[str])
def list_mailboxes_endpoint(
    x_agent_id: str | None = Header(default=None),
    service: AccessService = Depends(get_access_service)
):
    return service.mailboxes(x_agent_id)


@router.get("/api/mailboxes/{mailbox}/emails", response_model=list[MailboxEmail])
def list_mailbox_emails_endpoint(
    mailbox: str,
    batch_id: int | None = None,
    x_agent_id: str | None = Header(default=None),
    service: AccessService = Depends(get_access_service)
):
    return service.emails(x_agent_id, mailbox, batch_id)


@router.post("/api/mailboxes/{mailbox}/emails/{email_id}/review", response_model=ReviewAction)
def review_email_endpoint(
    mailbox: str,
    email_id: int,
    request: ReviewActionRequest,
    x_agent_id: str | None = Header(default=None),
    service: AccessService = Depends(get_access_service)
):
    return service.review(x_agent_id, mailbox, email_id, request.action, request.edited_reply)


@router.post("/api/agents", response_model=Agent, status_code=status.HTTP_201_CREATED)
def create_agent_endpoint(request: Agent, service: AccessService = Depends(get_access_service)):
    return service.create_agent(request.id, request.name)


@router.patch("/api/agents/{agent_id}", response_model=Agent)
def rename_agent_endpoint(
    agent_id: str, request: AgentRenameRequest, service: AccessService = Depends(get_access_service)
):
    return service.rename_agent(agent_id, request.name)


@router.delete("/api/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_agent_endpoint(agent_id: str, service: AccessService = Depends(get_access_service)):
    service.delete_agent(agent_id)


@router.get("/api/admin/mailboxes", response_model=list[str])
def list_all_mailboxes_endpoint(service: AccessService = Depends(get_access_service)):
    return service.list_mailboxes()


@router.post("/api/admin/mailboxes", status_code=status.HTTP_201_CREATED)
def create_mailbox_endpoint(request: MailboxCreateRequest, service: AccessService = Depends(get_access_service)):
    return {"name": service.create_mailbox(request.name)}


@router.delete("/api/admin/mailboxes/{name}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_mailbox_endpoint(name: str, service: AccessService = Depends(get_access_service)):
    service.delete_mailbox(name)


@router.post(
    "/api/admin/mailboxes/{mailbox}/assignments/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
)
def assign_mailbox_endpoint(mailbox: str, agent_id: str, service: AccessService = Depends(get_access_service)):
    service.assign(agent_id, mailbox)


@router.delete(
    "/api/admin/mailboxes/{mailbox}/assignments/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
)
def unassign_mailbox_endpoint(mailbox: str, agent_id: str, service: AccessService = Depends(get_access_service)):
    service.unassign(agent_id, mailbox)
