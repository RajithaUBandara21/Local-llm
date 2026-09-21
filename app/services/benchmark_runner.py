import csv
import os
from datetime import datetime
from app.config import RESULTS_DIR
from app.prompts import PROMPTS
from app.schemas import UniversalResponse
from app.services.inference import run_inference_with_retry

HEADERS = [
    "model", "prompt_id", "temperature", "run", "attempt", 
    "is_valid_json", "prompt", "reply", "error", "ttft_sec", 
    "latency_sec", "tokens_per_sec", "input_tokens", 
    "output_tokens", "cpu_percent", "ram_mb", "vram_mb"
]

def create_results_file():
    """Return the timestamped CSV path shared by every model in one benchmark run."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(RESULTS_DIR, f"benchmark_phase2_attempts_{timestamp}.csv")

def run_benchmark_for_model(model_name: str, csv_filename: str, temperatures: list[float], runs_per_prompt: int):
    """Run all prompts at the given temperatures for a specific model, appending to the run's CSV."""
    print(f"Starting Phase 2 Benchmark for model: {model_name}")
    print(f"Results will be saved to: {csv_filename}\n")

    with open(csv_filename, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS)
        # Append mode: the first model creates the file, later models must not repeat the header.
        if file.tell() == 0:
            writer.writeheader()

        for temp in temperatures:
            print(f"\n{'='*60}")
            print(f"TESTING TEMPERATURE: {temp} ON MODEL: {model_name}")
            print(f"{'='*60}")
            
            for prompt_id, prompt_text in PROMPTS.items():
                print(f"\n[Prompt {prompt_id}]: {prompt_text}")
                
                for run in range(1, runs_per_prompt + 1):
                    print(f"\n  --- Run {run}/{runs_per_prompt} ---")
                    
                    result = run_inference_with_retry(
                        model=model_name, 
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
                        
                        print(f"    Metrics: TTFT = {att['ttft_sec']}s | Total Latency = {att['latency_sec']}s | {att['tokens_per_sec']} t/s")
                    
                    for attempt_data in result["attempts_history"]:
                        row = {
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
                        }
                        writer.writerow(row)
                    
                    if result["final_success"]:
                        print(f"    >>> Status: PASSED (Resolved in {result['total_attempts']} attempt(s))\n")
                    else:
                        print(f"    >>> Status: FAILED (Graceful Failure: {result['message']})\n")
    
    print(f"\nBenchmark complete for {model_name}!")
