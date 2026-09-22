from fastapi import APIRouter, Depends, Header

from app.dependencies import get_access_service
from app.schemas import Agent, MailboxEmail, ReviewAction, ReviewActionRequest
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
