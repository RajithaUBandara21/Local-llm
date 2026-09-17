import json
import time

import requests

from config import OLLAMA_URL
from resource_monitor import capture_process_usage


def run_inference(model, prompt):
    """Run one streamed inference and return timing and resource metrics."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
    }

    start_time = time.time()
    first_token_time = None
    final_metrics = {}
    usage_before = capture_process_usage()

    try:
        response = requests.post(OLLAMA_URL, json=payload, stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            data = json.loads(line)
            if first_token_time is None and not data.get("done"):
                first_token_time = time.time()
            if data.get("done"):
                final_metrics = data

        end_time = time.time()
        usage_after = capture_process_usage()
        ttft = (first_token_time - start_time) if first_token_time else 0
        latency = end_time - start_time
        input_tokens = final_metrics.get("prompt_eval_count", 0)
        output_tokens = final_metrics.get("eval_count", 0)
        generation_time = latency - ttft
        tokens_per_sec = output_tokens / generation_time if generation_time > 0 else 0
        elapsed = max(latency, 0.001)
        cpu_percent = max(
            0,
            (usage_after["cpu_time"] - usage_before["cpu_time"]) / elapsed * 100,
        )

        return {
            "ttft": round(ttft, 4),
            "tokens_per_sec": round(tokens_per_sec, 2),
            "latency": round(latency, 4),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cpu_percent": round(cpu_percent, 2),
            "ram_mb": round(usage_after["ram_mb"], 2),
            "vram_mb": usage_after["vram_mb"],
            "success": True,
            "error": None,
        }
    except Exception as error:
        return {"success": False, "error": str(error)}
