import threading

from app.config import MODELS


class AppState:
    """Holds global application state."""

    def __init__(self):
        self.active_model: str = MODELS[0] if MODELS else "llama3.2"
        self.active_temperature: float = 0.7
        self.benchmark_running: bool = False
        self.active_batch_id: int | None = None
        # Set to a batch id to ask its running loop to pause after the current email.
        self.stop_batch_id: int | None = None
        # Held while a batch start or resume checks and claims the worker slot.
        self.batch_lock = threading.Lock()
        # The single in-flight Gmail OAuth attempt, if any; a new connect overwrites it,
        # so only the most recently started attempt's state token is ever valid.
        self.pending_gmail_oauth_state: str | None = None


global_state = AppState()


def get_app_state() -> AppState:
    return global_state
