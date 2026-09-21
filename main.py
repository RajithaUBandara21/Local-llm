import os
import csv
import glob
import requests
from abc import ABC, abstractmethod
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import MODELS, RESULTS_DIR, OLLAMA_URL
from benchmark import run_benchmark_for_model
app = FastAPI(title="SOLID AI Assistant & Benchmark API")



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# ==========================================
# 1. Entities & State
# ==========================================
class ChatRequest(BaseModel):
    prompt: str

class ModelChangeRequest(BaseModel):
    model_name: str

class TemperatureRequest(BaseModel):
    temperature: float

class AppState:
    """Holds global application state."""
    def __init__(self):
        self.active_model: str = MODELS[0] if MODELS else "llama3.2"
        self.active_temperature: float = 0.7
        self.benchmark_running: bool = False

# Singleton state instance
global_state = AppState()

def get_app_state() -> AppState:
    return global_state

# ==========================================
# 2. Interfaces (Dependency Inversion Principle)
# ==========================================
class ILLMClient(ABC):
    """Abstract interface for LLM interactions."""
    @abstractmethod
    def generate(self, model: str, prompt: str, temperature: float) -> dict: pass
    
    @abstractmethod
    def load_model(self, model: str) -> None: pass
    
    @abstractmethod
    def unload_model(self, model: str) -> None: pass

class IMetricsRepository(ABC):
    """Abstract interface for reading benchmark metrics."""
    @abstractmethod
    def get_latest_metrics(self) -> dict: pass

# ==========================================
# 3. Concrete Implementations (Single Responsibility Principle)
# ==========================================
class OllamaClient(ILLMClient):
    """Handles direct HTTP communication with the Ollama API."""
    def __init__(self, base_url: str):
        self.base_url = base_url

    def generate(self, model: str, prompt: str, temperature: float) -> dict:
        payload = {
            "model": model, "prompt": prompt, "stream": False, 
            "options": {"temperature": temperature}
        }
        response = requests.post(self.base_url, json=payload)
        response.raise_for_status()
        return response.json()

    def load_model(self, model: str) -> None:
        requests.post(self.base_url, json={"model": model, "keep_alive": -1}).raise_for_status()

    def unload_model(self, model: str) -> None:
        requests.post(self.base_url, json={"model": model, "keep_alive": 0}).raise_for_status()

class CSVMetricsRepository(IMetricsRepository):
    """Handles reading and parsing CSV files from the local filesystem."""
    def __init__(self, results_dir: str):
        self.results_dir = results_dir

    def get_latest_metrics(self) -> dict:
        if not os.path.exists(self.results_dir):
            raise FileNotFoundError("Results directory not found.")
        
        csv_files = glob.glob(os.path.join(self.results_dir, "*.csv"))
        if not csv_files:
            raise FileNotFoundError("No benchmark CSV files found.")
            
        latest_file = max(csv_files, key=os.path.getctime)
        metrics = []
        with open(latest_file, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                metrics.append(row)
                
        return {
            "latest_benchmark_file": os.path.basename(latest_file),
            "total_runs": len(metrics),
            "data": metrics
        }

# ==========================================
# 4. Services (Business Logic)
# ==========================================
class AssistantService:
    """Coordinates business rules using the injected LLM Client and State."""
    def __init__(self, client: ILLMClient, state: AppState):
        self.client = client
        self.state = state

    def process_chat(self, prompt: str) -> dict:
        try:
            return self.client.generate(self.state.active_model, prompt, self.state.active_temperature)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM Generation failed: {str(e)}")

    def switch_active_model(self, new_model: str) -> str:
        if new_model not in MODELS:
            raise HTTPException(status_code=400, detail=f"Model {new_model} not configured.")
        try:
            self.client.unload_model(self.state.active_model)
            self.client.load_model(new_model)
            self.state.active_model = new_model
            return new_model
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to switch models: {str(e)}")

    def update_temperature(self, temp: float) -> float:
        if not (0.0 <= temp <= 2.0):
            raise HTTPException(status_code=400, detail="Temperature must be between 0.0 and 2.0")
        self.state.active_temperature = temp
        return temp

class BenchmarkService:
    """Coordinates benchmark execution."""
    def __init__(self, state: AppState):
        self.state = state

    def run_pipeline(self):
        self.state.benchmark_running = True
        try:
            for model in MODELS:
                run_benchmark_for_model(model)
        finally:
            self.state.benchmark_running = False

# ==========================================
# 5. Dependency Injection Providers
# ==========================================
def get_llm_client() -> ILLMClient:
    return OllamaClient(OLLAMA_URL)

def get_metrics_repository() -> IMetricsRepository:
    return CSVMetricsRepository(RESULTS_DIR)

def get_assistant_service(
    client: ILLMClient = Depends(get_llm_client),
    state: AppState = Depends(get_app_state)
) -> AssistantService:
    return AssistantService(client, state)

def get_benchmark_service(state: AppState = Depends(get_app_state)) -> BenchmarkService:
    return BenchmarkService(state)

# ==========================================
# 6. FastAPI Controllers (Routers)
# ==========================================


@app.post("/api/chat")
def chat_endpoint(
    request: ChatRequest, 
    service: AssistantService = Depends(get_assistant_service)
):
    return service.process_chat(request.prompt)

@app.post("/api/model/change")
def change_model_endpoint(
    request: ModelChangeRequest, 
    service: AssistantService = Depends(get_assistant_service)
):
    new_model = service.switch_active_model(request.model_name)
    return {"status": "success", "message": f"Switched active model to {new_model}"}

@app.post("/api/settings/temperature")
def set_temperature_endpoint(
    request: TemperatureRequest, 
    service: AssistantService = Depends(get_assistant_service)
):
    new_temp = service.update_temperature(request.temperature)
    return {"status": "success", "active_temperature": new_temp}

@app.post("/api/benchmark/start")
def start_benchmark_endpoint(
    background_tasks: BackgroundTasks, 
    state: AppState = Depends(get_app_state),
    service: BenchmarkService = Depends(get_benchmark_service)
):
    if state.benchmark_running:
        raise HTTPException(status_code=400, detail="A benchmark is already running.")
    
    background_tasks.add_task(service.run_pipeline)
    return {"status": "Benchmark initiated in the background."}

@app.get("/api/benchmark/status")
def get_benchmark_status_endpoint(state: AppState = Depends(get_app_state)):
    return {"benchmark_running": state.benchmark_running}

@app.get("/health")
def health_check():
    """Simple health check endpoint to verify the API is running."""
    return {"status": "healthy", "service": "Local AI Assistant API"}

@app.get("/api/benchmark/metrics")
def get_dashboard_metrics_endpoint(
    repo: IMetricsRepository = Depends(get_metrics_repository)


    
):
    try:
        return repo.get_latest_metrics()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))