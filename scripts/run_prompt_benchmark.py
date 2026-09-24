"""Standalone prompt benchmark: no FastAPI server needed.

Edit scripts/benchmark_prompt_config.py, then run from the project root:

    python scripts/run_prompt_benchmark.py

Requires Ollama running locally with the configured models pulled. Writes a
timestamped CSV to RESULTS_DIR with per-attempt speed, resource, and JSON
validity measures for every model/temperature/prompt combination.
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.benchmark_prompt_config import (
    MODELS,
    PROMPT_IDS,
    RESULTS_DIR,
    RUNS_PER_PROMPT,
    TEMPERATURES,
)

from app.clients.ollama import OllamaClient
from app.config import OLLAMA_GENERATE_URL, OLLAMA_PS_URL, OLLAMA_TAGS_URL
from app.prompts import ALL_PROMPTS
from app.schemas import UniversalResponse
from app.services.inference import run_inference_with_retry
from app.services.model_loading import unload_others

HEADERS = [
    "model", "prompt_id", "temperature", "run", "attempt",
    "is_valid_json", "prompt", "reply", "error", "ttft_sec",
    "latency_sec", "tokens_per_sec", "input_tokens",
    "output_tokens", "cpu_percent", "ram_mb", "vram_mb",
]


def resolve_prompts() -> dict[str, str]:
    if PROMPT_IDS is None:
        return dict(ALL_PROMPTS)
    missing = [pid for pid in PROMPT_IDS if pid not in ALL_PROMPTS]
    if missing:
        raise SystemExit(f"Unknown prompt id(s) in PROMPT_IDS: {', '.join(missing)}")
    return {pid: ALL_PROMPTS[pid] for pid in PROMPT_IDS}


def create_results_file() -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(RESULTS_DIR, f"prompt_benchmark_{timestamp}.csv")


def run_for_model(model_name: str, csv_path: str, prompts: dict[str, str], writer: csv.DictWriter) -> None:
    print(f"Starting benchmark for model: {model_name}")

    for temp in TEMPERATURES:
        print(f"\n{'=' * 60}\nTEMPERATURE: {temp} | MODEL: {model_name}\n{'=' * 60}")

        for prompt_id, prompt_text in prompts.items():
            print(f"\n[Prompt {prompt_id}]: {prompt_text}")

            for run in range(1, RUNS_PER_PROMPT + 1):
                print(f"  --- Run {run}/{RUNS_PER_PROMPT} ---")
                result = run_inference_with_retry(
                    model=model_name, prompt=prompt_text, temp=temp, schema_class=UniversalResponse,
                )

                for attempt_data in result["attempts_history"]:
                    status = "VALID" if attempt_data["is_valid"] else "INVALID"
                    print(f"    [Attempt {attempt_data['attempt']}] ({status}) "
                          f"TTFT={attempt_data['ttft_sec']}s Latency={attempt_data['latency_sec']}s "
                          f"{attempt_data['tokens_per_sec']} t/s")
                    writer.writerow({
                        "model": model_name,
                        "prompt_id": prompt_id,
                        "temperature": temp,
                        "run": run,
                        "attempt": attempt_data["attempt"],
                        "is_valid_json": attempt_data["is_valid"],
                        "prompt": prompt_text,
                        "reply": attempt_data["reply"],
                        "error": attempt_data["error"],
                        "ttft_sec": attempt_data["ttft_sec"],
                        "latency_sec": attempt_data["latency_sec"],
                        "tokens_per_sec": attempt_data["tokens_per_sec"],
                        "input_tokens": attempt_data["input_tokens"],
                        "output_tokens": attempt_data["output_tokens"],
                        "cpu_percent": attempt_data["cpu_percent"],
                        "ram_mb": attempt_data["ram_mb"],
                        "vram_mb": attempt_data["vram_mb"],
                    })

                status = "PASSED" if result["final_success"] else "FAILED"
                print(f"    >>> Status: {status} ({result['total_attempts']} attempt(s))")

    print(f"\nBenchmark complete for {model_name}!")


def main() -> None:
    if not MODELS:
        raise SystemExit("MODELS is empty in scripts/benchmark_prompt_config.py")
    prompts = resolve_prompts()
    client = OllamaClient(OLLAMA_GENERATE_URL, OLLAMA_PS_URL, OLLAMA_TAGS_URL)
    csv_path = create_results_file()
    print(f"Results will be saved to: {csv_path}\n")

    with open(csv_path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS)
        writer.writeheader()

        for model in MODELS:
            unload_others(client, model)
            run_for_model(model, csv_path, prompts, writer)
            print(f"\n[RESOURCE OPTIMIZATION] Unloading {model} from VRAM...")
            try:
                client.unload_model(model)
                print(f"[RESOURCE OPTIMIZATION] {model} successfully unloaded.\n")
            except Exception as error:
                print(f"[RESOURCE OPTIMIZATION] Failed to unload {model}: {error}\n")

    print(f"\nAll done. Results at: {csv_path}")


if __name__ == "__main__":
    main()
