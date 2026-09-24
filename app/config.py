import os
from pathlib import Path
from typing import Dict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def read_env_file(path: Path) -> Dict[str, str]:
    """Parse KEY=VALUE lines; a missing or unreadable file yields no values."""
    try:
        # utf-8-sig drops the BOM that Windows editors add, which would otherwise
        # glue itself to the first key.
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}

    values: Dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_setting(name: str, default: str, env_file: Path = ENV_FILE) -> str:
    """Resolve a setting: real environment first, then the .env file, then the default."""
    if name in os.environ:
        return os.environ[name]
    return read_env_file(env_file).get(name, default)


OLLAMA_URL = load_setting("OLLAMA_URL", "http://localhost:11434").rstrip("/")
DATABASE_PATH = load_setting("DATABASE_PATH", "triage.db")
OLLAMA_GENERATE_URL = f"{OLLAMA_URL}/api/generate"
OLLAMA_PS_URL = f"{OLLAMA_URL}/api/ps"
OLLAMA_TAGS_URL = f"{OLLAMA_URL}/api/tags"

# Gmail OAuth (feature 26b). Empty client id/secret/key means Gmail is not configured;
# routes that need them return 503 instead of failing at import time.
GOOGLE_CLIENT_ID = load_setting("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = load_setting("GOOGLE_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI = load_setting(
    "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/gmail/oauth/callback"
)
GMAIL_TOKEN_ENCRYPTION_KEY = load_setting("GMAIL_TOKEN_ENCRYPTION_KEY", "")
ADMIN_DASHBOARD_URL = load_setting("ADMIN_DASHBOARD_URL", "http://localhost:3000/admin")

MODELS = ["llama3.2", "phi-4-Q4", "mistral-7b-q4", "mistral-7b-Q5"]
TEMPERATURES = [0.0, 0.7]
RUNS_PER_PROMPT = 3
# Upper bound for a per-request override, so a typo cannot start an enormous run.
MAX_RUNS_PER_PROMPT = 10
MAX_RETRIES = 3
RESULTS_DIR = "results"

# MAX_RETRIES above belongs to the benchmark and counts total attempts; triage has
# its own pair so one retry (two attempts) does not change benchmark behavior.
TRIAGE_MAX_ATTEMPTS = 2
TRIAGE_TIMEOUT_SEC = 30
# About 1500 tokens, so the prompt stays inside a small default context window
# instead of being silently truncated by Ollama.
TRIAGE_MAX_BODY_CHARS = 6000

# Batches load mailbox files from here; the API accepts only a bare file name inside it.
MAILBOX_DIR = "data"

# Caps a client-uploaded mailbox file, so a mistaken or hostile upload cannot fill the disk.
MAX_MAILBOX_UPLOAD_BYTES = 20 * 1024 * 1024
