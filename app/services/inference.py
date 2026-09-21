import time
import requests
import json
from typing import Type, List, Dict, Any
from pydantic import BaseModel
from app.config import OLLAMA_GENERATE_URL, MAX_RETRIES
from app.resource_monitor import capture_process_usage
from app.services.output_validator import OutputValidator

FALLBACK_MESSAGE = "Unable to generate a valid structured response. Please try again."

def run_inference_with_retry(
    model: str, 
    prompt: str, 
    temp: float, 
    schema_class: Type[BaseModel]
) -> Dict[str, Any]:
    """Run inference with streaming to capture TTFT, followed by structural validation."""
    schema_dict = schema_class.model_json_schema()
    attempts_history: List[Dict[str, Any]] = []
    current_prompt = prompt
    last_reply = ""

    for attempt in range(1, MAX_RETRIES + 1):
        payload = {
            "model": model,
            "prompt": current_prompt,
            "stream": True,  # Re-enabled to measure TTFT
            "format": schema_dict,
            "options": {"temperature": temp}
        }
        
        start_time = time.time()
        first_token_time = None
        usage_before = capture_process_usage()
        raw_reply = ""
        final_metrics = {}
        
        try:
            response = requests.post(OLLAMA_GENERATE_URL, json=payload, stream=True)
            response.raise_for_status()
            
            # Process the stream to calculate TTFT and build the raw reply
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                
                if first_token_time is None and not data.get("done"):
                    first_token_time = time.time()
                    
                raw_reply += data.get("response", "")
                
                if data.get("done"):
                    final_metrics = data
            
            end_time = time.time()
            usage_after = capture_process_usage()
            last_reply = raw_reply
            
            # Calculate Latency & TTFT
            ttft = (first_token_time - start_time) if first_token_time else (end_time - start_time)
            latency = end_time - start_time
            
            input_tokens = final_metrics.get("prompt_eval_count", 0)
            output_tokens = final_metrics.get("eval_count", 0)
            
            # Tokens per second based on generation time (excluding TTFT)
            generation_time = latency - ttft
            tokens_per_sec = output_tokens / generation_time if generation_time > 0 else 0
            
            elapsed = max(latency, 0.001)
            cpu_percent = max(0, (usage_after["cpu_time"] - usage_before["cpu_time"]) / elapsed * 100)
            
            # Validate the accumulated JSON string against Pydantic schema
            is_valid, parsed_data, error_msg = OutputValidator.validate_json(raw_reply, schema_class)
            
            attempt_record = {
                "attempt": attempt,
                "prompt_used": current_prompt,
                "reply": raw_reply,
                "is_valid": is_valid,
                "error": error_msg,
                "ttft_sec": round(ttft, 4),
                "latency_sec": round(latency, 4),
                "tokens_per_sec": round(tokens_per_sec, 2),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cpu_percent": round(cpu_percent, 2),
                "ram_mb": round(usage_after["ram_mb"], 2),
                "vram_mb": usage_after["vram_mb"],
            }
            attempts_history.append(attempt_record)
            
            if is_valid:
                return {
                    "final_success": True,
                    "total_attempts": attempt,
                    "reply": raw_reply,
                    "data": parsed_data,
                    "message": "Success",
                    "attempts_history": attempts_history
                }
            
            # Prepare feedback prompt for next attempt
            current_prompt = (
                f"{prompt}\n\n"
                f"[SYSTEM FEEDBACK]: Your previous response failed schema validation.\n"
                f"Issues found:\n{error_msg}\n"
                f"Output ONLY valid JSON matching the schema."
            )
            
        except Exception as error:
            last_reply = raw_reply if raw_reply else str(error)
            attempts_history.append({
                "attempt": attempt,
                "prompt_used": current_prompt,
                "reply": last_reply,
                "is_valid": False,
                "error": str(error),
                "ttft_sec": 0,
                "latency_sec": 0,
                "tokens_per_sec": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cpu_percent": 0,
                "ram_mb": 0,
                "vram_mb": 0,
            })

    return {
        "final_success": False,
        "total_attempts": MAX_RETRIES,
        "reply": last_reply,
        "data": None,
        "message": FALLBACK_MESSAGE,
        "attempts_history": attempts_history
    }