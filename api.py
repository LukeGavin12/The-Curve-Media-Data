"""
FastAPI entry point for Railway.

Exposes HTTP endpoints so the admin app can trigger pipeline stages.
The APScheduler daily job starts in a background thread on startup.
"""

import os
import threading
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException

from ingestion.scheduler import run_ingestion, start_scheduler
from filtering.filter import run_filtering
from clustering.cluster import run_clustering
from scoring.score import run_scoring

API_KEY = os.environ.get("PIPELINE_API_KEY", "")


def _check_key(x_api_key: str) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=start_scheduler, daemon=True)
    thread.start()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run/ingest")
def run_ingest(background_tasks: BackgroundTasks, x_api_key: str = Header(default="")):
    _check_key(x_api_key)
    background_tasks.add_task(run_ingestion)
    return {"status": "started"}


@app.post("/run/filter")
def run_filter(background_tasks: BackgroundTasks, date: str | None = None, x_api_key: str = Header(default="")):
    _check_key(x_api_key)
    background_tasks.add_task(run_filtering, run_date=date)
    return {"status": "started"}


@app.post("/run/cluster")
def run_cluster(background_tasks: BackgroundTasks, date: str | None = None, x_api_key: str = Header(default="")):
    _check_key(x_api_key)
    background_tasks.add_task(run_clustering, run_date=date)
    return {"status": "started"}


@app.post("/run/score")
def run_score(background_tasks: BackgroundTasks, date: str | None = None, x_api_key: str = Header(default="")):
    _check_key(x_api_key)
    background_tasks.add_task(run_scoring, run_date=date)
    return {"status": "started"}
