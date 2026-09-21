from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import access, assistant, batches, benchmark, health, triage
from app.startup import seed_directory


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_directory()
    yield


app = FastAPI(title="SOLID AI Assistant & Benchmark API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(access.router)
app.include_router(assistant.router)
app.include_router(batches.router)
app.include_router(benchmark.router)
app.include_router(health.router)
app.include_router(triage.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
