"""Standalone mail-set (batch) benchmark: no FastAPI server needed.

Edit scripts/mailset_benchmark_config.py, then run from the project root:

    python scripts/run_mailset_benchmark.py

Requires Ollama running locally with the configured models pulled. Runs triage
on every email in MAIL_SET_CSV for each model/temperature, scores category and
priority against the CSV's own ground-truth columns, and writes a timestamped
CSV to RESULTS_DIR with per-email speed, resource, validity, and accuracy
measures.
"""

import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.mailset_benchmark_config import (
    MAIL_SET_CSV,
    MAX_ATTEMPTS,
    MAX_EMAILS,
    MODELS,
    RESULTS_DIR,
    TEMPERATURES,
    TIMEOUT_SEC,
)

from app.clients.base import LLMTimeoutError
from app.clients.ollama import OllamaClient
from app.config import OLLAMA_GENERATE_URL, OLLAMA_PS_URL, OLLAMA_TAGS_URL
from app.loaders.cleaner import clean_body, looks_like_html
from app.prompts import build_triage_prompt, build_triage_retry_prompt
from app.resource_monitor import capture_process_usage
from app.schemas import TriageResult
from app.services.model_loading import unload_others
from app.services.output_validator import OutputValidator

HEADERS = [
    "model", "temperature", "email_id", "attempt",
    "is_valid_json", "sender", "subject",
    "true_category", "true_priority",
    "pred_category", "pred_priority", "category_correct", "priority_correct",
    "confidence", "flags", "error", "latency_sec",
    "cpu_percent", "ram_mb", "vram_mb",
]


class LabeledEmail:
    def __init__(self, row_id: int, sender: str, subject: str, body: str, category: str, priority: str):
        self.id = row_id
        self.sender = sender
        self.subject = subject
        self.body = body
        self.category = category
        self.priority = priority


def load_labeled_emails(path: str) -> list[LabeledEmail]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise SystemExit(f"MAIL_SET_CSV not found: {csv_path}")

    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = ("sender", "subject", "body", "category", "priority")
        missing = [column for column in required if column not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"MAIL_SET_CSV is missing required columns: {', '.join(missing)}")

        emails = []
        for row_number, row in enumerate(reader, start=1):
            body = row.get("body") or ""
            emails.append(LabeledEmail(
                row_id=row_number,
                sender=(row.get("sender") or "").strip(),
                subject=(row.get("subject") or "").strip(),
                body=clean_body(body, is_html=looks_like_html(body)),
                category=(row.get("category") or "").strip(),
                priority=(row.get("priority") or "").strip(),
            ))

    if MAX_EMAILS is not None:
        emails = emails[:MAX_EMAILS]
    return emails


def create_results_file() -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(RESULTS_DIR, f"mailset_benchmark_{timestamp}.csv")


def triage_one(client: OllamaClient, model: str, temperature: float, email: LabeledEmail) -> list[dict]:
    """Run triage for one email; returns one row dict per attempt made."""
    prompt = build_triage_prompt(email.sender, email.subject, email.body)
    schema = TriageResult.model_json_schema()
    attempt_prompt = prompt
    rows = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        started = time.perf_counter()
        usage_before = capture_process_usage()
        try:
            reply = client.generate(
                model, attempt_prompt, temperature, schema=schema, timeout=TIMEOUT_SEC,
            )
        except LLMTimeoutError:
            rows.append(_row(email, attempt, False, error=f"Timed out after {TIMEOUT_SEC}s",
                              latency=time.perf_counter() - started, usage_before=usage_before))
            break
        except Exception as error:
            rows.append(_row(email, attempt, False, error=str(error),
                              latency=time.perf_counter() - started, usage_before=usage_before))
            break

        latency = time.perf_counter() - started
        usage_after = capture_process_usage()
        is_valid, data, error_text = OutputValidator.validate_json(reply.get("response", ""), TriageResult)
        rows.append(_row(
            email, attempt, is_valid, error=error_text, latency=latency,
            usage_before=usage_before, usage_after=usage_after, data=data,
        ))
        if is_valid:
            break
        attempt_prompt = build_triage_retry_prompt(prompt, error_text)

    return rows


def _row(email: LabeledEmail, attempt: int, is_valid: bool, error, latency, usage_before,
         usage_after=None, data=None) -> dict:
    elapsed = max(latency, 0.001)
    cpu_percent = 0.0
    ram_mb = 0.0
    vram_mb = None
    if usage_after is not None:
        cpu_percent = max(0.0, (usage_after["cpu_time"] - usage_before["cpu_time"]) / elapsed * 100)
        ram_mb = usage_after["ram_mb"]
        vram_mb = usage_after["vram_mb"]

    pred_category = data.get("category") if data else None
    pred_priority = data.get("priority") if data else None
    return {
        "email_id": email.id,
        "attempt": attempt,
        "is_valid_json": is_valid,
        "sender": email.sender,
        "subject": email.subject,
        "true_category": email.category,
        "true_priority": email.priority,
        "pred_category": pred_category,
        "pred_priority": pred_priority,
        "category_correct": (pred_category == email.category) if data else None,
        "priority_correct": (pred_priority == email.priority) if data else None,
        "confidence": data.get("confidence") if data else None,
        "flags": ";".join(data.get("flags", [])) if data else None,
        "error": error,
        "latency_sec": round(latency, 4),
        "cpu_percent": round(cpu_percent, 2),
        "ram_mb": round(ram_mb, 2),
        "vram_mb": vram_mb,
    }


def run_for_model(client: OllamaClient, model: str, emails: list[LabeledEmail], writer: csv.DictWriter) -> None:
    print(f"Starting mail-set benchmark for model: {model}")
    unload_others(client, model)
    client.load_model(model)

    for temperature in TEMPERATURES:
        print(f"\n{'=' * 60}\nTEMPERATURE: {temperature} | MODEL: {model}\n{'=' * 60}")
        correct_category = 0
        correct_priority = 0
        scored = 0

        for index, email in enumerate(emails, start=1):
            print(f"  [{index}/{len(emails)}] Email {email.id}: {email.subject[:60]!r}")
            rows = triage_one(client, model, temperature, email)
            for row in rows:
                writer.writerow({**row, "model": model, "temperature": temperature})
            final = rows[-1]
            if final["category_correct"] is not None:
                scored += 1
                correct_category += int(final["category_correct"])
                correct_priority += int(final["priority_correct"])

        if scored:
            print(f"\n  Category accuracy: {correct_category}/{scored} "
                  f"({100 * correct_category / scored:.1f}%)")
            print(f"  Priority accuracy: {correct_priority}/{scored} "
                  f"({100 * correct_priority / scored:.1f}%)")

    print(f"\n[RESOURCE OPTIMIZATION] Unloading {model} from VRAM...")
    try:
        client.unload_model(model)
        print(f"[RESOURCE OPTIMIZATION] {model} successfully unloaded.\n")
    except Exception as error:
        print(f"[RESOURCE OPTIMIZATION] Failed to unload {model}: {error}\n")


def main() -> None:
    if not MODELS:
        raise SystemExit("MODELS is empty in scripts/mailset_benchmark_config.py")
    emails = load_labeled_emails(MAIL_SET_CSV)
    if not emails:
        raise SystemExit(f"No emails loaded from {MAIL_SET_CSV}")
    print(f"Loaded {len(emails)} labeled emails from {MAIL_SET_CSV}")

    client = OllamaClient(OLLAMA_GENERATE_URL, OLLAMA_PS_URL, OLLAMA_TAGS_URL)
    csv_path = create_results_file()
    print(f"Results will be saved to: {csv_path}\n")

    with open(csv_path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS)
        writer.writeheader()
        for model in MODELS:
            run_for_model(client, model, emails, writer)

    print(f"\nAll done. Results at: {csv_path}")


if __name__ == "__main__":
    main()
