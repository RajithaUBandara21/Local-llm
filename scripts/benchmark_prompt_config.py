# Config for scripts/run_prompt_benchmark.py. Edit and re-run; no server needed.

# Ollama must be running with each of these models pulled.
MODELS = ["llama3.2", "phi-4-Q4", "mistral-7b-q4", "mistral-7b-Q5"]

TEMPERATURES = [0.0, 0.7]

# How many times each prompt runs per model/temperature combination.
RUNS_PER_PROMPT = 3

# Subset of app.prompts.ALL_PROMPTS ids to run, or None for every prompt.
PROMPT_IDS = None

# Where the timestamped output CSV is written.
RESULTS_DIR = "results"
