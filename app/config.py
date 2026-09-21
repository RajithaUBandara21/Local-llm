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
OLLAMA_GENERATE_URL = f"{OLLAMA_URL}/api/generate"

MODELS = ["llama3.2", "phi-4-Q4", "mistral-7b-q4", "mistral-7b-Q5"]
TEMPERATURES = [0.0, 0.7]
RUNS_PER_PROMPT = 3
MAX_RETRIES = 3
RESULTS_DIR = "results"
