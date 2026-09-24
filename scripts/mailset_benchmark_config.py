# Config for scripts/run_mailset_benchmark.py. Edit and re-run; no server needed.

# Ollama must be running with each of these models pulled.
MODELS = ["llama3.2", "phi-4-Q4", "mistral-7b-q4", "mistral-7b-Q5"]

TEMPERATURES = [0.0, 0.7]

# Labeled mail set: must have sender, subject, body, received_at, category,
# priority columns (data/northport_emails.csv is the shipped ground truth set).
MAIL_SET_CSV = "data/northport_emails.csv"

# Cap how many emails from MAIL_SET_CSV are used, or None for all of them.
MAX_EMAILS = None

# Retries per email before giving up (mirrors app.config.TRIAGE_MAX_ATTEMPTS).
MAX_ATTEMPTS = 2

# Seconds to wait for one model reply before treating it as a timeout.
TIMEOUT_SEC = 30

# Where the timestamped output CSV is written.
RESULTS_DIR = "results"
