import pytest
import requests
from fastapi import HTTPException

from app.repositories.sqlite_gmail import SQLiteGmailRepository
from app.services import gmail_oauth as gmail_oauth_module
from app.services.gmail_oauth import GmailOAuthService
from app.state import AppState


class FakeCredentials:
    def __init__(self, refresh_token="refresh-token-value", id_token="id-token-value"):
        self.refresh_token = refresh_token
        self.id_token = id_token


class FakeFlow:
    """Stands in for google_auth_oauthlib.flow.Flow: records calls, returns fixed values."""

    def __init__(self, credentials=None):
        self.credentials = credentials or FakeCredentials()
        self.fetched_code = None

    def authorization_url(self, **kwargs):
        self.authorization_kwargs = kwargs
        return "https://accounts.google.com/o/oauth2/auth?mock=1", None

    def fetch_token(self, code):
        self.fetched_code = code


@pytest.fixture
def gmail(tmp_path):
    return SQLiteGmailRepository(tmp_path / "triage.db")


@pytest.fixture
def state():
    return AppState()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(gmail_oauth_module, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(gmail_oauth_module, "GOOGLE_CLIENT_SECRET", "client-secret")
    from cryptography.fernet import Fernet

    monkeypatch.setattr(gmail_oauth_module, "GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())


def service(gmail, state):
    return GmailOAuthService(gmail, state)


def test_build_authorization_url_503s_when_gmail_is_not_configured(gmail, state):
    with pytest.raises(HTTPException) as exc_info:
        service(gmail, state).build_authorization_url()
    assert exc_info.value.status_code == 503


def test_build_authorization_url_stores_pending_state_and_returns_the_url(gmail, state, configured, monkeypatch):
    fake_flow = FakeFlow()
    monkeypatch.setattr(gmail_oauth_module, "_build_flow", lambda: fake_flow)

    url = service(gmail, state).build_authorization_url()

    assert url == "https://accounts.google.com/o/oauth2/auth?mock=1"
    assert state.pending_gmail_oauth_state == fake_flow.authorization_kwargs["state"]
    assert fake_flow.authorization_kwargs["access_type"] == "offline"
    assert fake_flow.authorization_kwargs["prompt"] == "consent"


def test_complete_authorization_400s_when_no_attempt_is_pending(gmail, state):
    with pytest.raises(HTTPException) as exc_info:
        service(gmail, state).complete_authorization(code="abc", state="whatever")
    assert exc_info.value.status_code == 400


def test_complete_authorization_400s_on_a_state_mismatch(gmail, state):
    state.pending_gmail_oauth_state = "expected-state"

    with pytest.raises(HTTPException) as exc_info:
        service(gmail, state).complete_authorization(code="abc", state="wrong-state")
    assert exc_info.value.status_code == 400


def test_complete_authorization_saves_the_connection_and_clears_pending_state(
    gmail, state, configured, monkeypatch
):
    state.pending_gmail_oauth_state = "expected-state"
    fake_flow = FakeFlow()
    monkeypatch.setattr(gmail_oauth_module, "_build_flow", lambda: fake_flow)
    monkeypatch.setattr(
        gmail_oauth_module.id_token, "verify_oauth2_token", lambda *args, **kwargs: {"email": "person@example.com"}
    )

    service(gmail, state).complete_authorization(code="auth-code", state="expected-state")

    assert fake_flow.fetched_code == "auth-code"
    assert state.pending_gmail_oauth_state is None
    connection = gmail.get_gmail_connection()
    assert connection.email == "person@example.com"

    from cryptography.fernet import Fernet

    stored_token = gmail.get_gmail_refresh_token()
    decrypted = Fernet(gmail_oauth_module.GMAIL_TOKEN_ENCRYPTION_KEY.encode()).decrypt(stored_token)
    assert decrypted == b"refresh-token-value"


def test_status_reflects_the_stored_connection(gmail, state, configured, monkeypatch):
    assert service(gmail, state).status() is None

    gmail.save_gmail_connection("person@example.com", b"encrypted")
    connection = service(gmail, state).status()
    assert connection.email == "person@example.com"


def test_disconnect_when_nothing_was_connected_succeeds_without_calling_revoke(gmail, state, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("requests.post should not be called when nothing is connected")

    monkeypatch.setattr(gmail_oauth_module.requests, "post", fail_if_called)

    service(gmail, state).disconnect()
    assert gmail.get_gmail_connection() is None


def test_disconnect_revokes_then_deletes_when_revoke_succeeds(gmail, state, configured, monkeypatch):
    from cryptography.fernet import Fernet

    key = gmail_oauth_module.GMAIL_TOKEN_ENCRYPTION_KEY
    gmail.save_gmail_connection("person@example.com", Fernet(key.encode()).encrypt(b"the-refresh-token"))
    calls = []
    monkeypatch.setattr(
        gmail_oauth_module.requests, "post", lambda url, params, timeout: calls.append((url, params))
    )

    service(gmail, state).disconnect()

    assert calls == [(gmail_oauth_module.GOOGLE_REVOKE_URL, {"token": "the-refresh-token"})]
    assert gmail.get_gmail_connection() is None


def test_disconnect_still_deletes_locally_when_revoke_raises(gmail, state, configured, monkeypatch):
    from cryptography.fernet import Fernet

    key = gmail_oauth_module.GMAIL_TOKEN_ENCRYPTION_KEY
    gmail.save_gmail_connection("person@example.com", Fernet(key.encode()).encrypt(b"the-refresh-token"))

    def raise_connection_error(*args, **kwargs):
        raise requests.RequestException("network is down")

    monkeypatch.setattr(gmail_oauth_module.requests, "post", raise_connection_error)

    service(gmail, state).disconnect()
    assert gmail.get_gmail_connection() is None


def test_disconnect_still_deletes_locally_when_the_encryption_key_is_invalid(gmail, state, monkeypatch):
    monkeypatch.setattr(gmail_oauth_module, "GMAIL_TOKEN_ENCRYPTION_KEY", "not-a-valid-fernet-key")
    gmail.save_gmail_connection("person@example.com", b"encrypted-under-a-different-key")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("requests.post should not be called when the key cannot decrypt the token")

    monkeypatch.setattr(gmail_oauth_module.requests, "post", fail_if_called)

    service(gmail, state).disconnect()
    assert gmail.get_gmail_connection() is None
