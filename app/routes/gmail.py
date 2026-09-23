import logging

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.config import ADMIN_DASHBOARD_URL
from app.dependencies import get_gmail_oauth_service
from app.schemas import GmailConnectRequest, GmailConnection
from app.services.gmail_oauth import GmailOAuthService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/gmail/oauth/connect")
def connect_gmail_endpoint(
    request: GmailConnectRequest, service: GmailOAuthService = Depends(get_gmail_oauth_service)
):
    authorization_url = service.build_authorization_url(request.mailbox)
    return {"authorization_url": authorization_url}


@router.get("/api/gmail/oauth/callback")
def gmail_oauth_callback_endpoint(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    service: GmailOAuthService = Depends(get_gmail_oauth_service),
):
    if error or not code or not state:
        return RedirectResponse(url=f"{ADMIN_DASHBOARD_URL}?gmail_status=error")
    try:
        service.complete_authorization(code=code, state=state)
    except Exception as exc:
        logger.warning("Gmail OAuth callback failed: %s", exc)
        return RedirectResponse(url=f"{ADMIN_DASHBOARD_URL}?gmail_status=error")
    return RedirectResponse(url=f"{ADMIN_DASHBOARD_URL}?gmail_status=connected")


@router.get("/api/gmail/status", response_model=GmailConnection | None)
def gmail_status_endpoint(service: GmailOAuthService = Depends(get_gmail_oauth_service)):
    return service.status()


@router.post("/api/gmail/oauth/disconnect", status_code=204)
def disconnect_gmail_endpoint(service: GmailOAuthService = Depends(get_gmail_oauth_service)):
    service.disconnect()
