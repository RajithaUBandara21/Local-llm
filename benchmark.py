import csv
import os
from datetime import datetime
from config import (
    MODEL_NAME, 
    PROMPTS, 
    RESULTS_DIR, 
    RUNS_PER_PROMPT, 
    TEMPERATURES, 
    UniversalResponse
)
from inference import run_inference_with_retry

HEADERS = [
    "model",
    "prompt_id",
    "temperature",
    "run",
    "attempt",
    "is_valid_json",
    "prompt",
    "reply",
    "error",
    "ttft_sec",
    "latency_sec",
    "tokens_per_sec",
    "input_tokens",
    "output_tokens",
    "cpu_percent",
    "ram_mb",
    "vram_mb"
]

def create_results_file():
    """Create the timestamped CSV file used by this benchmark run."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(RESULTS_DIR, f"benchmark_phase2_attempts_{MODEL_NAME}_{timestamp}.csv")

def run_benchmark():
    """Run all prompts across temperatures, logging and printing replies and timing metrics."""
    csv_filename = create_results_file()
    print(f"Starting Phase 2 Benchmark for model: {MODEL_NAME}")
    print(f"Results will be saved to: {csv_filename}\n")
    
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS)
        writer.writeheader()
        
        for temp in TEMPERATURES:
            print(f"\n{'='*60}")
            print(f"TESTING TEMPERATURE: {temp}")
            print(f"{'='*60}")
            
            for prompt_id, prompt_text in PROMPTS.items():
                print(f"\n[Prompt {prompt_id}]: {prompt_text}")
                
                for run in range(1, RUNS_PER_PROMPT + 1):
                    print(f"\n  --- Run {run}/{RUNS_PER_PROMPT} ---")
                    
                    result = run_inference_with_retry(
                        model=MODEL_NAME, 
                        prompt=prompt_text, 
                        temp=temp, 
                        schema_class=UniversalResponse
                    )
                    
                    for att in result["attempts_history"]:
                        status = "VALID" if att["is_valid"] else "INVALID"
                        print(f"    [Attempt {att['attempt']}] ({status}):")
                        
                        reply_display = att["reply"] if att["reply"] else "<EMPTY RESPONSE>"
                        print(f"    Reply: {reply_display}")
                        
                        if not att["is_valid"]:
                            print(f"    Error: {att['error']}")
                        
                        # Print TTFT and Latency dynamically
                        print(f"    Metrics: TTFT = {att['ttft_sec']}s | Total Latency = {att['latency_sec']}s | {att['tokens_per_sec']} t/s")
                    
                    for attempt_data in result["attempts_history"]:
                        row = {
                            "model": MODEL_NAME,
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
                        }
                        writer.writerow(row)
                    
                    if result["final_success"]:
                        print(f"    >>> Status: PASSED (Resolved in {result['total_attempts']} attempt(s))\n")
                    else:
                        print(f"    >>> Status: FAILED (Graceful Failure: {result['message']})\n")

    print("\nBenchmark complete! All attempts, replies, and latency metrics have been recorded.")

if __name__ == "__main__":
    run_benchmark()