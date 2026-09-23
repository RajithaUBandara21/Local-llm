import pytest
import requests
from fastapi import HTTPException

from app.repositories.sqlite_access import SQLiteAccessRepository
from app.schemas import Agent, Seed
from app.services import gmail_oauth as gmail_oauth_module
from app.services.gmail_oauth import GmailOAuthService
from app.state import AppState

SEED = Seed(agents=[Agent(id="asha", name="Asha")], assignments={"support": ["asha"], "refunds": []})


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
def access(tmp_path):
    repository = SQLiteAccessRepository(tmp_path / "triage.db")
    repository.replace_directory(SEED)
    return repository


@pytest.fixture
def state():
    return AppState()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(gmail_oauth_module, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(gmail_oauth_module, "GOOGLE_CLIENT_SECRET", "client-secret")
    from cryptography.fernet import Fernet

    monkeypatch.setattr(gmail_oauth_module, "GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())


def service(access, state):
    return GmailOAuthService(access, state)


def test_build_authorization_url_404s_for_an_unknown_mailbox(access, state, configured):
    with pytest.raises(HTTPException) as exc_info:
        service(access, state).build_authorization_url("ghost-mailbox")
    assert exc_info.value.status_code == 404


def test_build_authorization_url_503s_when_gmail_is_not_configured(access, state):
    with pytest.raises(HTTPException) as exc_info:
        service(access, state).build_authorization_url("support")
    assert exc_info.value.status_code == 503


def test_build_authorization_url_stores_pending_state_and_returns_the_url(access, state, configured, monkeypatch):
    fake_flow = FakeFlow()
    monkeypatch.setattr(gmail_oauth_module, "_build_flow", lambda: fake_flow)

    url = service(access, state).build_authorization_url("support")

    assert url == "https://accounts.google.com/o/oauth2/auth?mock=1"
    assert state.pending_gmail_oauth_mailbox == "support"
    assert state.pending_gmail_oauth_state == fake_flow.authorization_kwargs["state"]
    assert fake_flow.authorization_kwargs["access_type"] == "offline"
    assert fake_flow.authorization_kwargs["prompt"] == "consent"


def test_complete_authorization_400s_when_no_attempt_is_pending(access, state):
    with pytest.raises(HTTPException) as exc_info:
        service(access, state).complete_authorization(code="abc", state="whatever")
    assert exc_info.value.status_code == 400


def test_complete_authorization_400s_on_a_state_mismatch(access, state):
    state.pending_gmail_oauth_state = "expected-state"
    state.pending_gmail_oauth_mailbox = "support"

    with pytest.raises(HTTPException) as exc_info:
        service(access, state).complete_authorization(code="abc", state="wrong-state")
    assert exc_info.value.status_code == 400


def test_complete_authorization_saves_the_connection_and_clears_pending_state(
    access, state, configured, monkeypatch
):
    state.pending_gmail_oauth_state = "expected-state"
    state.pending_gmail_oauth_mailbox = "support"
    fake_flow = FakeFlow()
    monkeypatch.setattr(gmail_oauth_module, "_build_flow", lambda: fake_flow)
    monkeypatch.setattr(
        gmail_oauth_module.id_token, "verify_oauth2_token", lambda *args, **kwargs: {"email": "agent@example.com"}
    )

    service(access, state).complete_authorization(code="auth-code", state="expected-state")

    assert fake_flow.fetched_code == "auth-code"
    assert state.pending_gmail_oauth_state is None
    assert state.pending_gmail_oauth_mailbox is None
    connection = access.get_gmail_connection()
    assert connection.mailbox == "support"
    assert connection.email == "agent@example.com"

    from cryptography.fernet import Fernet

    stored_token = access.get_gmail_refresh_token()
    decrypted = Fernet(gmail_oauth_module.GMAIL_TOKEN_ENCRYPTION_KEY.encode()).decrypt(stored_token)
    assert decrypted == b"refresh-token-value"


def test_status_reflects_the_stored_connection(access, state, configured, monkeypatch):
    assert service(access, state).status() is None

    access.save_gmail_connection("support", "agent@example.com", b"encrypted")
    connection = service(access, state).status()
    assert connection.mailbox == "support"
    assert connection.email == "agent@example.com"


def test_disconnect_when_nothing_was_connected_succeeds_without_calling_revoke(access, state, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("requests.post should not be called when nothing is connected")

    monkeypatch.setattr(gmail_oauth_module.requests, "post", fail_if_called)

    service(access, state).disconnect()
    assert access.get_gmail_connection() is None


def test_disconnect_revokes_then_deletes_when_revoke_succeeds(access, state, configured, monkeypatch):
    from cryptography.fernet import Fernet

    key = gmail_oauth_module.GMAIL_TOKEN_ENCRYPTION_KEY
    access.save_gmail_connection(
        "support", "agent@example.com", Fernet(key.encode()).encrypt(b"the-refresh-token")
    )
    calls = []
    monkeypatch.setattr(
        gmail_oauth_module.requests, "post", lambda url, params, timeout: calls.append((url, params))
    )

    service(access, state).disconnect()

    assert calls == [(gmail_oauth_module.GOOGLE_REVOKE_URL, {"token": "the-refresh-token"})]
    assert access.get_gmail_connection() is None


def test_disconnect_still_deletes_locally_when_revoke_raises(access, state, configured, monkeypatch):
    from cryptography.fernet import Fernet

    key = gmail_oauth_module.GMAIL_TOKEN_ENCRYPTION_KEY
    access.save_gmail_connection(
        "support", "agent@example.com", Fernet(key.encode()).encrypt(b"the-refresh-token")
    )

    def raise_connection_error(*args, **kwargs):
        raise requests.RequestException("network is down")

    monkeypatch.setattr(gmail_oauth_module.requests, "post", raise_connection_error)

    service(access, state).disconnect()
    assert access.get_gmail_connection() is None


def test_disconnect_still_deletes_locally_when_the_encryption_key_is_invalid(access, state, monkeypatch):
    monkeypatch.setattr(gmail_oauth_module, "GMAIL_TOKEN_ENCRYPTION_KEY", "not-a-valid-fernet-key")
    access.save_gmail_connection("support", "agent@example.com", b"encrypted-under-a-different-key")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("requests.post should not be called when the key cannot decrypt the token")

    monkeypatch.setattr(gmail_oauth_module.requests, "post", fail_if_called)

    service(access, state).disconnect()
    assert access.get_gmail_connection() is None
