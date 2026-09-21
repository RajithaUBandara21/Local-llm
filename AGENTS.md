# AGENTS.md

Instructions for AI coding agents working in this project.

AI tools must not add AI attribution to commits or pull requests, including AI
`Co-Authored-By` trailers or generated-by signatures. Preserve genuine human
attribution.

## What this is

A local LLM assistant and benchmark service. A FastAPI backend wraps
[Ollama](https://ollama.com) so a client can chat with a chosen local model,
switch models, adjust temperature, and run a benchmark that measures each model's
speed, resource use, and structured-output reliability. Benchmark results are
written to CSV files under `results/`. `Front end/prototype.html` is a static
Bootstrap dashboard prototype that calls the API.

## Stack

- Python 3.13, virtual environment in `.venv/`, packages installed with `pip`
- FastAPI + Uvicorn (API), Pydantic v2 (request models and LLM output schema)
- `requests` (blocking HTTP to Ollama), `psutil` and `nvidia-smi` (resource metrics)
- `pytest` (unit tests)
- Ollama running at `http://localhost:11434` with the configured models pulled
- No database; state is in memory and benchmark output is CSV

## Layout

`app/` is the package; each module has one responsibility and dependencies point
inward (routes, then services, then interfaces).

- `app/main.py` - FastAPI app, CORS, routers, and the `python -m app.main` runner
- `app/config.py` - the only module that reads `.env` or the environment; Ollama
  URL and fixed tuning constants (models, temperatures, retries, results dir)
- `app/prompts.py` - benchmark prompts and `ACTIVE_PROMPT_IDS`, the switch for
  which ones run
- `app/schemas.py` - request models and the `UniversalResponse` LLM schema
- `app/state.py` - in-memory `AppState`
- `app/dependencies.py` - `Depends` providers, the one place concrete
  implementations are chosen
- `app/routes/` - HTTP handlers only (`assistant`, `benchmark`, `health`)
- `app/services/` - business rules (`assistant`, `benchmark`), the benchmark
  runner, streaming inference with schema validation and retry, and
  `output_validator`
- `app/clients/` - `ILLMClient` and `OllamaClient`
- `app/repositories/` - `IMetricsRepository` and `CSVMetricsRepository`
- `app/resource_monitor.py` - CPU, RAM, and VRAM sampling for the Ollama process tree
- `tests/` - pytest unit tests; `pytest.ini` puts the project root on the import path
- `results/` - benchmark CSV output (timestamped per model and run)
- `.env.example` - tracked list of settings; copy to the git-ignored `.env`
- `Front end/prototype.html` - static dashboard prototype

## Settings

`OLLAMA_URL` is the Ollama base URL (default `http://localhost:11434`, no path).
It comes from a real environment variable, then `.env`, then the default, and is
read only in `app/config.py`.

## Proportional engineering

Build for established requirements, not hypothetical scale, threats, or future
flexibility. Reuse existing code, the standard library, native platform features,
and installed dependencies before adding machinery.

- Unknown scale or extensibility defaults to the smaller reversible design. Do
  not infer enterprise, multi-tenant, hostile-user, or compliance requirements.
- Derive trust and data-integrity boundaries from actual reachability: untrusted
  input, auth/session/ownership, shared persisted data, destructive operations,
  payments, secrets, and sensitive data.
- Ask only when an unknown materially changes behavior, architecture, persisted
  data, interoperability, a real security boundary, or cost. Otherwise choose the
  simplest repository-native implementation.
- Add an abstraction, dependency, service, configuration surface, compatibility
  layer, or security mechanism only for a current requirement.
- Simplicity never removes real trust-boundary validation, data-loss prevention,
  accessibility, explicit security requirements, configured tests, or project rules.

## Conventions

- `snake_case` for modules, functions, and variables; `PascalCase` for classes;
  `SCREAMING_SNAKE_CASE` for constants (kept in `app/config.py`); `I` prefix for
  abstract interfaces (`ILLMClient`)
- Type-hint function signatures; use Pydantic models for request bodies and LLM
  output schemas
- Write modular code that follows the SOLID principles: one responsibility per
  module and class, services depend on interfaces, and concrete implementations
  are injected with FastAPI `Depends`
- Keep HTTP handling in route functions, business rules in service classes, and
  external I/O (Ollama, files, SQLite) behind an interface
- All routes live under `/api/...`, plus `/health`
- Deployment settings such as the Ollama URL belong in a git-ignored `.env` file
  read through one config module (a `.env.example` is tracked)
- Only one Ollama model is loaded at a time; unload the others before using one
- Use only the models already installed in Ollama
- Raise `HTTPException` for client and upstream errors (400 bad input, 404 missing
  results, 500 wrapped failures); do not let raw exceptions reach the client
- Comment the why, not the what; no commented-out code; no unused imports
- No em dashes (U+2014) in docs, comments, or commit messages

## Commands

Windows, from the project root.

- Create the environment (once): `python -m venv .venv`
- Activate it: `.venv\Scripts\activate`
- Install dependencies: `pip install -r requirements.txt`
- Dev server: `uvicorn app.main:app --reload --port 8000` (`http://localhost:8000`,
  interactive docs at `/docs`, health at `/health`); `python -m app.main` does the same
- Benchmark: start it with `POST /api/benchmark/start`; there is no standalone
  command-line entry point
- Test: `python -m pytest` (needs no Ollama or GPU)
- Build: none
- Lint: none configured

Ollama must be running with the models named in `app/config.py` available before chat
or benchmark calls will succeed.

## Testing

pytest is set up and the `test` command above is the gate. The suite covers
`OutputValidator.validate_json`, the retry flow in `app/services/inference.py`
(with `requests` and resource sampling mocked), `CSVMetricsRepository` (against
temporary directories), the `.env` config loader, the prompt switch,
`AssistantService`, `BenchmarkService`, and the benchmark route functions (called
directly with fakes, since `httpx` for `TestClient` is not installed).
`OllamaClient`, `benchmark_runner`, and `resource_monitor` are not covered. Do not unit test live Ollama,
`nvidia-smi`, or the static dashboard; verify those by running the app.

No `Verify` command or GitHub workflow exists yet.
