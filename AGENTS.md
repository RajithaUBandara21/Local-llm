# AGENTS.md

Instructions for AI coding agents working in this project.

AI tools must not add AI attribution to commits or pull requests, including AI
`Co-Authored-By` trailers or generated-by signatures. Preserve genuine human
attribution.

## What this is

A local LLM assistant and email-triage service. A FastAPI backend wraps
[Ollama](https://ollama.com) so a client can chat with a chosen local model,
switch models, adjust temperature, and triage batches of support emails.
`scripts/` has standalone, non-API benchmark tools (prompt and mail-set) that
measure a model's speed, resource use, and structured-output reliability,
writing timestamped CSV files under `results/`. `Front end/prototype.html` is a
static Bootstrap dashboard prototype that calls the API.

## Stack

- Python 3.13, virtual environment in `.venv/`, packages installed with `pip`
- FastAPI + Uvicorn (API), Pydantic v2 (request models and LLM output schema)
- `requests` (blocking HTTP to Ollama), `psutil` and `nvidia-smi` (resource metrics)
- `pytest` (unit tests)
- Ollama running at `http://localhost:11434` with the configured models pulled
- SQLite (standard library `sqlite3`) for batches, emails, triage results, and the
  decision log; other state is in memory and standalone benchmark output is CSV

## Layout

`app/` is the package; each module has one responsibility and dependencies point
inward (routes, then services, then interfaces).

- `app/main.py` - FastAPI app, CORS, routers, and the `python -m app.main` runner
- `app/config.py` - the only module that reads `.env` or the environment; Ollama
  URL and fixed tuning constants (models, temperatures, retries, triage attempts,
  timeout, and body cap)
- `app/prompts.py` - the standalone-benchmark prompts and `ACTIVE_PROMPT_IDS`, the
  switch for which ones run, plus the triage prompt and retry-prompt builders
- `app/schemas.py` - request models, the `UniversalResponse` schema used by the
  standalone prompt benchmark, and the triage models (`TriageRequest`,
  `TriageResult`, `TriageResponse`)
- `app/state.py` - in-memory `AppState`
- `app/dependencies.py` - `Depends` providers, the one place concrete
  implementations are chosen
- `app/routes/` - HTTP handlers only (`assistant`, `batches`, `gmail`, `health`,
  `triage`)
- `app/services/` - business rules (`assistant`, `batch`, `gmail_oauth`, `triage`),
  streaming inference with schema validation and retry, `output_validator`, and
  `model_loading` (unloads every loaded model except the one about to be used)
- `app/clients/` - `ILLMClient` (its `generate` takes an optional JSON schema and
  timeout; a timeout raises `LLMTimeoutError`) and `OllamaClient`
- `app/repositories/` - `IBatchRepository` and `SQLiteBatchRepository` (schema,
  results, decision log); `IGmailRepository` and `SQLiteGmailRepository` (the
  single stored Gmail connection); `sqlite_connection` (the shared connection helper)
- `app/loaders/` - mailbox file loaders: `IEmailLoader` and `EmailLoadError`,
  `CsvEmailLoader` and `MboxEmailLoader`, the body `cleaner`, and the extension
  `factory`
- `app/resource_monitor.py` - CPU, RAM, and VRAM sampling for the Ollama process tree
- `tests/` - pytest unit tests; `pytest.ini` puts the project root on the import path
- `scripts/` - standalone prompt and mail-set benchmark entry points
  (`run_prompt_benchmark.py`, `run_mailset_benchmark.py`) and their config files;
  no FastAPI server or route calls them
- `results/` - standalone benchmark CSV output (timestamped per model and run)
- `data/` - `northport_emails.csv`, 100 labeled synthetic support emails (ground
  truth for triage evaluation), and a README with the columns and labeling rules
- `.env.example` - tracked list of settings; copy to the git-ignored `.env`
- `docs/` - written deliverables: `discovery-brief.md` and `architecture.md`
- `Front end/prototype.html` - static dashboard prototype
- `web/` - the review page: Next.js (TypeScript, App Router), calling the
  FastAPI backend directly from the browser (CORS already allows any origin).
  `app/` holds the routed page and the ported theme (`globals.css`, from
  `prototypes/theme.css`); `lib/` holds the typed API client (`api.ts`,
  `types.ts`) and the review-queue state (React context); `components/` holds
  the small, single-responsibility UI pieces (queue and manual-review panels,
  detail panel, action bar, batch status)

## Settings

`OLLAMA_URL` is the Ollama base URL (default `http://localhost:11434`, no path).
It comes from a real environment variable, then `.env`, then the default, and is
read only in `app/config.py`.

`DATABASE_PATH` is the SQLite file for batches and triage results (default
`triage.db` in the working directory, git-ignored). It resolves the same way.

`NEXT_PUBLIC_API_URL` is the FastAPI base URL the `web/` app calls (default
`http://localhost:8000`). It lives in `web/.env.local`, git-ignored like the
backend's `.env`; a tracked `web/.env.local.example` documents it.

Gmail OAuth (feature 26b) is configured by four more `.env` settings, all
optional: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` (from a Google Cloud
OAuth client), `GOOGLE_OAUTH_REDIRECT_URI` (default
`http://localhost:8000/api/gmail/oauth/callback`), and
`GMAIL_TOKEN_ENCRYPTION_KEY` (a base64 `Fernet` key encrypting the stored
refresh token at rest). Leaving `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, or
`GMAIL_TOKEN_ENCRYPTION_KEY` blank disables Gmail connect (503) without
affecting the rest of the app. `ADMIN_DASHBOARD_URL` (default
`http://localhost:3000/admin`) is where the OAuth callback redirects the
browser after connecting.

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
- Standalone prompt benchmark: `python scripts/run_prompt_benchmark.py` (edit
  `scripts/benchmark_prompt_config.py` first); standalone mail-set benchmark:
  `python scripts/run_mailset_benchmark.py` (edit
  `scripts/mailset_benchmark_config.py` first). Neither needs the FastAPI server.
- Test: `python -m pytest` (needs no Ollama or GPU)
- Build: none
- Lint: none configured

Ollama must be running with the models named in `app/config.py` available before chat,
triage, or benchmark script calls will succeed.

Review page (`web/`), Windows, from `web/`.

- Install dependencies (once): `npm install`
- Dev server: `npm run dev` (`http://localhost:3000`; needs the FastAPI server
  running for its API calls to succeed)
- Build: `npm run build`
- Lint: `npm run lint`
- Test: none configured (see Testing)

## Testing

pytest is set up and the `test` command above is the gate. The suite covers
`OutputValidator.validate_json`, the retry flow in `app/services/inference.py`
(with `requests` and resource sampling mocked), the `.env` config loader, the
prompt switch, `AssistantService`, `unload_others` in
`app/services/model_loading.py`, `SQLiteBatchRepository` (real SQLite files in
temporary directories), `BatchService` (crash and resume, guards including
overlapping starts, file-name checks), `SQLiteGmailRepository`, `GmailOAuthService`
(connect, callback, status, disconnect, revoke-on-disconnect paths), the email
cleaner, `CsvEmailLoader`, `MboxEmailLoader`, and the loader factory (against
temporary files), and the triage, gmail, and batch route functions (called
directly with fakes, since `httpx` for `TestClient` is not installed).
Triage is covered by the schema rules, the prompt builders, `TriageService`
(every retry, timeout, and failure branch), and `OllamaClient.generate` (with
`requests` mocked). `tests/test_dataset.py` checks the real
`data/northport_emails.csv` (structure, labels, cleaner round trip). The shared
fake `ILLMClient` is `tests/fakes.py`.
The other `OllamaClient` methods, `resource_monitor`, and the standalone
`scripts/` benchmarks are not covered. Do not unit test live Ollama, `nvidia-smi`,
or the static dashboard; verify those by running the app.

`web/` has no JS test runner; the same rule applies. `npm run build` (TypeScript
check plus the Next.js build) is its gate. Verify its behavior by running
`npm run dev` against the live FastAPI server.

No `Verify` command or GitHub workflow exists yet.
