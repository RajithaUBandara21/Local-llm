# Architecture

How the offline email triage assistant is put together, why, and what it
deliberately leaves to people. Each component is marked `built` (in the repo
today) or `planned` (in the build plan, not written yet). No triage accuracy or
speed figures appear here because triage evaluation has not run.

## Overview

```text
Mailbox files (mbox / CSV)
        |
        v
Loader + Cleaner (strip signatures, quoted replies, HTML)
        |
        v
Batch queue (process N emails, track status, resume on crash)
        |
        v
Ollama (local model) --> JSON output
        |
        v
Pydantic validation --(invalid)--> retry once --(still invalid)--> manual review queue
        |
        v
SQLite
        |
        v
FastAPI + review page (agent approves, edits, or rejects)
```

An email file is loaded and cleaned, queued in a batch, sent to a small local
model through Ollama, and the JSON reply is validated against a strict schema
before anything downstream sees it. Results are stored in SQLite and shown to a
support agent, who approves, edits, or rejects each draft. Nothing is sent
anywhere. The whole path runs on one machine with no external network calls.

## Components

| Stage | Where it lives | Status |
| --- | --- | --- |
| HTTP API (chat, model switch, temperature, benchmark, health) | `app/routes/`, `app/main.py` | built |
| Schema-validated inference with feedback retry and streaming metrics | `app/services/inference.py`, `app/services/output_validator.py` | built |
| Ollama access behind an interface | `app/clients/ollama.py` | built |
| One model loaded at a time | `app/services/model_loading.py` | built |
| CPU, RAM, and VRAM sampling | `app/resource_monitor.py` | built |
| Benchmark runner and CSV output | `app/services/benchmark_runner.py`, `app/repositories/csv_metrics.py` | built |
| Settings (Ollama URL, models, retries) | `app/config.py` | built |
| Email loader and cleaner | not yet written | planned |
| Batch queue with resume on crash | not yet written | planned |
| Triage endpoint, `POST /api/triage` | not yet written | planned |
| SQLite storage and decision log | not yet written | planned |
| Simulated identity and mailbox permissions | not yet written | planned |
| Agent review page | not yet written | planned |
| Benchmark dashboard | not yet written | planned |
| Docker Compose deployment with structured logs | not yet written | planned |

Dependencies point inward: routes call services, services call interfaces
(`ILLMClient`, `IMetricsRepository`), and the concrete implementations are
chosen in one place, `app/dependencies.py`. Triage will follow the same shape.

## Data flow

1. An agent or script supplies a mailbox file (mbox or CSV). `planned`
2. The loader parses it and the cleaner strips signatures, quoted replies, and
   HTML, leaving a clean body per email. `planned`
3. The emails become a batch with a status, so a crash resumes instead of
   restarting. `planned`
4. Each email is sent to the active Ollama model with the triage schema as the
   required output format. Before the call, every other loaded model is
   unloaded. The streamed call already exists for benchmarking. `built` for the
   call, `planned` for the triage prompt
5. The reply is validated with Pydantic. Invalid output gets one retry with the
   validation errors fed back. Output that is still invalid, or a timeout, goes
   to the manual review queue. `built` for validate-and-retry, `planned` for the
   triage limits
6. The result and a decision log entry (email id, model, latency, outcome) are
   written to SQLite. `planned`
7. The agent sees only the mailboxes assigned to them and approves, edits, or
   rejects each draft. `planned`

## Output schema

The model must return this shape (Pydantic model, `planned`):

| Field | Type | Rule |
| --- | --- | --- |
| `category` | enum | `refund`, `delivery`, `billing`, `complaint`, `inquiry`, `spam`, `other` |
| `priority` | enum | `urgent`, `high`, `normal`, `low` |
| `summary` | string | one or two sentences |
| `suggested_reply` | string or null | null when `out_of_policy` is flagged |
| `confidence` | float | 0.0 to 1.0 |
| `flags` | list of enum | `stale_context`, `out_of_policy`; may be empty |
| `flag_reason` | string or null | required when `flags` is not empty |

Manual review is decided by the pipeline after failed validation or a timeout,
never by the model. The general benchmark keeps its own schema, `UniversalResponse`.

Priority rules: category is independent of priority. Priority comes from money or
legal exposure, time-sensitivity, and repeat contact. When unsure between two
levels the higher one wins, and spam is always low.

## Decisions and trade-offs

| Decision | Alternative | What is given up |
| --- | --- | --- |
| Run a model locally through Ollama | Hosted model API | Model quality and speed headroom. Gains privacy, no per-call cost, and offline operation |
| Small model (the installed 3B to 14.7B models) | Larger model | Some accuracy, especially on ambiguous emails. Gains a model that fits a no-GPU machine |
| SQLite | Postgres | Concurrent writers. Fine for 1,500 emails a week and one operator; revisit only if concurrency demands it |
| Batch table in SQLite | Message broker or task queue | Throughput scaling and multiple workers. Gains one fewer service and simple resume |
| Validate, then retry once, then manual review | More retries | A few recoverable emails go to a person. Bounds latency per email and keeps the queue moving |
| Simulated agent identity, permissions enforced on the server | Real authentication or SSO | Real identity. Fine for internal trusted users and a demo; the server check is still the real boundary |
| Ollama on the host | Ollama inside the container | A self-contained container. Gains the existing installation and model files without duplicating multi-GB models |
| One model loaded at a time | Several loaded models | Some warm-up time on a switch. Gains measurements that belong to one model and fits small RAM |
| Human approves every draft | Auto-send | Speed. Removes the risk of a wrong or out-of-policy reply reaching a customer |
| Synthetic emails only | Real customer mail | Realism. Avoids PII entirely; labels are made ahead of time with Claude, never at runtime |

## Permissions, retries, and timeouts

- **Permissions:** each agent sees only assigned mailboxes. The seed data has
  four agents and three mailboxes: support (all four), refunds (two agents), and
  deliveries (two agents). The check is on the server, and denials are logged.
  `planned`
- **Retries:** triage makes two attempts in total, meaning one retry. In
  `app/config.py`, `MAX_RETRIES` is 3 and counts total attempts, and it applies
  to the benchmark path today. The triage spec will define its own constant.
- **Timeout:** the model call gets 30 seconds, then the email is marked failed,
  goes to manual review, and the batch continues. The current inference call has
  no timeout, so this is `planned`.
- **Logging:** every decision records email id, model, latency, and outcome.
  `planned`

## Failure modes

Each of these is the expected behavior, planned and to be verified in the
failure-case evaluation. None has been tested yet.

| # | Case | Expected behavior |
| --- | --- | --- |
| 1 | Stale data: the email refers to an old thread or expired order | Flag `stale_context`; the draft does not assert stale facts |
| 2 | Invalid structure: broken JSON | Retry once, then manual review; the batch continues |
| 3 | Timeout: Ollama stops or hangs mid-batch | Mark failed, resume the remaining emails, log the event |
| 4 | No permission: an agent opens an unassigned mailbox | Access denied and logged; no data returned |
| 5 | Out of policy: the email asks for legal or medical advice | Flag `out_of_policy`, no draft, reason recorded |

## Deliberately not automated

- Sending replies. A person approves every draft and nothing is sent.
- Legal, medical, or financial advice. These emails are flagged for a person.
- Deleting or archiving emails.

## Before production

- A GPU or a larger model, if accuracy or latency on the target machine falls
  short.
- Single sign-on and real authentication in place of the simulated identity.
- Monitoring and alerting on batch failures, timeouts, and manual-review volume.
- IMAP ingestion, so mail is pulled directly instead of loaded from files.
- An active-learning loop that feeds agent edits and rejections back into
  evaluation.

## Known limitations

- VRAM reads 0 on every successful run, because `nvidia-smi` reports no
  per-process memory on Windows. VRAM is not reported.
- `phi-4-Q4` is the full 14.7B Phi-4 (9.1 GB), so 5 seconds per email on a CPU
  is unlikely. This will be reported honestly.
- The two Mistral files are different versions (v0.3 at Q4, v0.1 at Q5), so a
  Q4 versus Q5 comparison is indicative, not controlled.
- Undecided: the web stack for the review page and dashboard, a bulk unlabeled
  file for batch and throughput tests (the labeled set is 100 emails), and the
  storage format of the labeled ground truth.
