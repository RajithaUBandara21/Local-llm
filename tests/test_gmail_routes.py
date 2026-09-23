import pytest
from fastapi import HTTPException

from app.routes.gmail import (
    connect_gmail_endpoint,
    disconnect_gmail_endpoint,
    gmail_oauth_callback_endpoint,
    gmail_status_endpoint,
)
from app.schemas import GmailConnectRequest, GmailConnection


class FakeGmailOAuthService:
    def __init__(self, authorization_url=None, connect_error=None, complete_error=None, connection=None):
        self.authorization_url = authorization_url
        self.connect_error = connect_error
        self.complete_error = complete_error
        self.connection = connection
        self.completed_with = None
        self.disconnected = False

    def build_authorization_url(self, mailbox):
        if self.connect_error:
            raise self.connect_error
        self.requested_mailbox = mailbox
        return self.authorization_url

    def complete_authorization(self, code, state):
        if self.complete_error:
            raise self.complete_error
        self.completed_with = (code, state)

    def status(self):
        return self.connection

    def disconnect(self):
        self.disconnected = True


def test_connect_endpoint_returns_the_authorization_url():
    service = FakeGmailOAuthService(authorization_url="https://accounts.google.com/o/oauth2/auth?mock=1")

    result = connect_gmail_endpoint(GmailConnectRequest(mailbox="support"), service)

    assert result == {"authorization_url": "https://accounts.google.com/o/oauth2/auth?mock=1"}
    assert service.requested_mailbox == "support"


def test_connect_endpoint_propagates_404_and_503():
    not_found = FakeGmailOAuthService(connect_error=HTTPException(status_code=404, detail="no such mailbox"))
    with pytest.raises(HTTPException) as exc_info:
        connect_gmail_endpoint(GmailConnectRequest(mailbox="ghost"), not_found)
    assert exc_info.value.status_code == 404

    unconfigured = FakeGmailOAuthService(connect_error=HTTPException(status_code=503, detail="not configured"))
    with pytest.raises(HTTPException) as exc_info:
        connect_gmail_endpoint(GmailConnectRequest(mailbox="support"), unconfigured)
    assert exc_info.value.status_code == 503


def test_callback_redirects_to_connected_on_success():
    service = FakeGmailOAuthService()

    response = gmail_oauth_callback_endpoint(code="auth-code", state="the-state", error=None, service=service)

    assert response.status_code == 307
    assert response.headers["location"].endswith("?gmail_status=connected")
    assert service.completed_with == ("auth-code", "the-state")


def test_callback_redirects_to_error_when_google_reports_an_error():
    service = FakeGmailOAuthService()

    response = gmail_oauth_callback_endpoint(code=None, state=None, error="access_denied", service=service)

    assert response.status_code == 307
    assert response.headers["location"].endswith("?gmail_status=error")
    assert service.completed_with is None


def test_callback_redirects_to_error_when_code_or_state_is_missing():
    service = FakeGmailOAuthService()

    response = gmail_oauth_callback_endpoint(code=None, state="the-state", error=None, service=service)

    assert response.headers["location"].endswith("?gmail_status=error")
    assert service.completed_with is None


def test_callback_redirects_to_error_when_the_service_raises_on_a_state_mismatch():
    service = FakeGmailOAuthService(
        complete_error=HTTPException(status_code=400, detail="Gmail connection attempt expired or is invalid.")
    )

    response = gmail_oauth_callback_endpoint(code="auth-code", state="wrong-state", error=None, service=service)

    assert response.status_code == 307
    assert response.headers["location"].endswith("?gmail_status=error")


def test_status_endpoint_returns_none_or_the_connection():
    disconnected = FakeGmailOAuthService(connection=None)
    assert gmail_status_endpoint(disconnected) is None

    connection = GmailConnection(mailbox="support", email="agent@example.com", connected_at="2026-01-01T00:00:00Z")
    connected = FakeGmailOAuthService(connection=connection)
    assert gmail_status_endpoint(connected) == connection


def test_disconnect_endpoint_always_succeeds():
    service = FakeGmailOAuthService()

    assert disconnect_gmail_endpoint(service) is None
    assert service.disconnected is True
