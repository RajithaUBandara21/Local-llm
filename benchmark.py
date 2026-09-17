import csv
import os
from datetime import datetime
from pydantic import BaseModel, ValidationError
from typing import List

from config import MODEL_NAME, PROMPTS, RESULTS_DIR, RUNS_PER_PROMPT
from inference import run_inference

HEADERS = [
    "model",
    "prompt_id",
    "run",
    "ttft_sec",
    "tokens_per_sec",
    "latency_sec",
    "input_tokens",
    "output_tokens",
    "cpu_percent",
    "ram_mb",
    "vram_mb",
]


def create_results_file():
    """Create the timestamped CSV file used by this benchmark run."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(RESULTS_DIR, f"benchmark_{MODEL_NAME}_{timestamp}.csv")


def metrics_row(prompt_id, run, metrics):
    """Convert inference metrics into the benchmark CSV schema."""
    return {
        "model": MODEL_NAME,
        "prompt_id": prompt_id,
        "run": run,
        "ttft_sec": metrics["ttft"],
        "tokens_per_sec": metrics["tokens_per_sec"],
        "latency_sec": metrics["latency"],
        "input_tokens": metrics["input_tokens"],
        "output_tokens": metrics["output_tokens"],
        "cpu_percent": metrics["cpu_percent"],
        "ram_mb": metrics["ram_mb"],
        "vram_mb": metrics["vram_mb"],
    }


def run_benchmark():
    """Run every configured prompt and write successful runs to CSV."""
    csv_filename = create_results_file()
    print(f"Starting benchmark for model: {MODEL_NAME}")
    print(f"Results will be saved to: {csv_filename}\n")

    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS)
        writer.writeheader()

        for prompt_id, prompt_text in PROMPTS.items():
            print(f"Testing Prompt {prompt_id}: '{prompt_text}'")
            for run in range(1, RUNS_PER_PROMPT + 1):
                print(f"  -> Run {run}/{RUNS_PER_PROMPT}...", end="", flush=True)
                metrics = run_inference(MODEL_NAME, prompt_text)

                if metrics["success"]:
                    writer.writerow(metrics_row(prompt_id, run, metrics))
                    print(
                        f" Done (TTFT: {metrics['ttft']}s | "
                        f"{metrics['tokens_per_sec']} t/s)"
                    )
                else:
                    print(f" Failed: {metrics['error']}")

    print("\nBenchmark complete!")


if __name__ == "__main__":
    run_benchmark()
