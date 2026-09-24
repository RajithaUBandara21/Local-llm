import logging
import secrets

import requests
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from app.config import (
    GMAIL_TOKEN_ENCRYPTION_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_OAUTH_REDIRECT_URI,
)
from app.repositories.base import IGmailRepository
from app.schemas import GmailConnection
from app.state import AppState

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


def _require_configured() -> None:
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GMAIL_TOKEN_ENCRYPTION_KEY):
        raise HTTPException(status_code=503, detail="Gmail is not configured on this server.")


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_OAUTH_REDIRECT_URI],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=GOOGLE_OAUTH_REDIRECT_URI)


class GmailOAuthService:
    """Runs the Gmail OAuth connect/status/disconnect flow; never touches the Gmail API itself."""

    def __init__(self, gmail: IGmailRepository, state: AppState):
        self.gmail = gmail
        self.state = state

    def build_authorization_url(self) -> str:
        _require_configured()
        state_token = secrets.token_urlsafe(32)
        flow = _build_flow()
        authorization_url, _ = flow.authorization_url(
            access_type="offline", prompt="consent", state=state_token
        )
        self.state.pending_gmail_oauth_state = state_token
        return authorization_url

    def complete_authorization(self, code: str, state: str) -> None:
        if not self.state.pending_gmail_oauth_state or state != self.state.pending_gmail_oauth_state:
            raise HTTPException(
                status_code=400, detail="Gmail connection attempt expired or is invalid; try connecting again."
            )
        try:
            flow = _build_flow()
            flow.fetch_token(code=code)
            credentials = flow.credentials
            claims = id_token.verify_oauth2_token(credentials.id_token, GoogleAuthRequest(), GOOGLE_CLIENT_ID)
            email = claims["email"]
            encrypted_refresh_token = Fernet(GMAIL_TOKEN_ENCRYPTION_KEY.encode()).encrypt(
                credentials.refresh_token.encode()
            )
            self.gmail.save_gmail_connection(email, encrypted_refresh_token)
        finally:
            self.state.pending_gmail_oauth_state = None

    def status(self) -> GmailConnection | None:
        return self.gmail.get_gmail_connection()

    def disconnect(self) -> None:
        self._revoke_best_effort()
        self.gmail.delete_gmail_connection()

    def _revoke_best_effort(self) -> None:
        encrypted_refresh_token = self.gmail.get_gmail_refresh_token()
        if encrypted_refresh_token is None:
            return
        try:
            refresh_token = Fernet(GMAIL_TOKEN_ENCRYPTION_KEY.encode()).decrypt(encrypted_refresh_token).decode()
            requests.post(GOOGLE_REVOKE_URL, params={"token": refresh_token}, timeout=10)
        except (requests.RequestException, InvalidToken, ValueError):
            logger.warning("Gmail token revoke request failed; disconnecting locally anyway.")
