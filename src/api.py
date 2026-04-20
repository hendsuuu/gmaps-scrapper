"""
FastAPI service that exposes the scraper to the Next.js frontend.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .exporters import build_base_name, save_records
    from .scraper import GoogleMapsScraper, load_proxies
    from .utils import sanitise_text, setup_logging
except ImportError:  # pragma: no cover - fallback for direct script execution
    from exporters import build_base_name, save_records
    from scraper import GoogleMapsScraper, load_proxies
    from utils import sanitise_text, setup_logging


setup_logging()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROXIES_FILE = PROJECT_ROOT / "proxies.txt"

app = FastAPI(
    title="Leads Scrapper API",
    version="1.0.0",
    description="Backend API for running Google Maps scraping jobs with progress tracking.",
)

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGIN",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScrapeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=120)
    location: str = Field(..., min_length=1, max_length=160)
    max_results: int = Field(default=20, ge=1, le=120)
    headless: bool = True
    language: str = Field(default="en", min_length=2, max_length=10)


jobs: dict[str, dict] = {}
jobs_lock = asyncio.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_progress(stage: str, message: str, processed: int, found: int, total: int) -> dict:
    if stage == "completed":
        percent = 100
    elif total > 0:
        percent = min(99, round((processed / total) * 100))
    elif stage == "collecting":
        percent = 8
    else:
        percent = 0

    return {
        "stage": stage,
        "message": message,
        "processed": processed,
        "found": found,
        "total": total,
        "percent": percent,
        "updated_at": now_iso(),
    }


async def set_job(job_id: str, **fields) -> None:
    async with jobs_lock:
        jobs[job_id].update(fields)


async def update_job_progress(job_id: str, payload: dict) -> None:
    async with jobs_lock:
        progress = build_progress(
            stage=payload.get("stage", "running"),
            message=payload.get("message", ""),
            processed=int(payload.get("processed", 0)),
            found=int(payload.get("found", 0)),
            total=int(payload.get("total", 0)),
        )
        if payload.get("current_name"):
            progress["current_name"] = payload["current_name"]
        jobs[job_id]["progress"] = progress


async def get_job(job_id: str) -> dict:
    async with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(
                status_code=404, detail="Scrape job not found.")
        return copy.deepcopy(job)


def prepare_record(record: dict, query: str, location: str) -> dict:
    prepared = dict(record)
    prepared["search_query"] = query
    prepared["search_location"] = location
    prepared["name"] = sanitise_text(prepared.get("name", ""))
    prepared["address"] = sanitise_text(prepared.get("address", ""))
    return prepared


# Thread pool for Playwright (Windows needs ProactorEventLoop for subprocesses)
_scraper_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="scraper",
)


async def run_scrape_job(job_id: str, request: ScrapeRequest) -> None:
    await set_job(
        job_id,
        status="running",
        started_at=now_iso(),
        progress=build_progress(
            stage="collecting",
            message="Preparing browser and proxy configuration.",
            processed=0,
            found=0,
            total=0,
        ),
    )

    try:
        proxy_list = load_proxies(str(PROXIES_FILE))
        scraper = GoogleMapsScraper(
            max_results=request.max_results,
            headless=request.headless,
            language=request.language,
            proxy_list=proxy_list,
        )

        # Run Playwright in a dedicated thread with its own event loop.
        # On Windows the main uvicorn loop may not support subprocess_exec
        # which Playwright needs to launch the browser process.
        main_loop = asyncio.get_running_loop()

        def _scrape_in_thread():
            if sys.platform == "win32":
                loop = asyncio.ProactorEventLoop()
            else:
                loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _progress(payload):
                fut = asyncio.run_coroutine_threadsafe(
                    update_job_progress(job_id, payload), main_loop,
                )
                fut.result(timeout=15)

            try:
                return loop.run_until_complete(
                    scraper.scrape(
                        query=request.query,
                        location=request.location,
                        progress_callback=_progress,
                    )
                )
            finally:
                loop.close()

        leads = await main_loop.run_in_executor(_scraper_pool, _scrape_in_thread)

        records = [
            prepare_record(lead.to_dict(), request.query, request.location)
            for lead in leads
        ]

        base_name = build_base_name(request.query, request.location)
        saved_files = save_records(records, base_name, PROJECT_ROOT)
        latest_job = await get_job(job_id)
        latest_progress = latest_job.get("progress", {})
        processed = int(latest_progress.get("processed", len(records)))
        total = int(latest_progress.get("total", processed))

        await set_job(
            job_id,
            status="completed",
            finished_at=now_iso(),
            results=records,
            output_files=saved_files,
            progress=build_progress(
                stage="completed",
                message=f"Finished scraping with {len(records)} leads ready.",
                processed=processed,
                found=len(records),
                total=total,
            ),
        )
    except Exception as exc:
        logger.exception("Scrape job %s failed", job_id)
        await set_job(
            job_id,
            status="failed",
            finished_at=now_iso(),
            error=str(exc),
            progress=build_progress(
                stage="failed",
                message="Scraping stopped because the backend hit an error.",
                processed=0,
                found=0,
                total=0,
            ),
        )


@app.get("/")
async def root():
    return {"message": "API jalan"}


@app.get("/api/health")
async def healthcheck() -> dict:
    return {
        "status": "ok",
        "service": "leads-scrapper-backend",
        "frontend_origins": frontend_origins,
    }


@app.post("/api/scrape/jobs")
async def create_scrape_job(request: ScrapeRequest) -> dict:
    job_id = uuid4().hex
    job = {
        "job_id": job_id,
        "status": "queued",
        "query": request.query,
        "location": request.location,
        "max_results": request.max_results,
        "created_at": now_iso(),
        "started_at": None,
        "finished_at": None,
        "error": None,
        "results": [],
        "output_files": None,
        "progress": build_progress(
            stage="queued",
            message="Your scrape job is queued.",
            processed=0,
            found=0,
            total=0,
        ),
    }

    async with jobs_lock:
        jobs[job_id] = job

    asyncio.create_task(run_scrape_job(job_id, request))
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/scrape/jobs/{job_id}")
async def read_scrape_job(job_id: str) -> dict:
    return await get_job(job_id)


# ---- History endpoints ----

JSON_DIR = PROJECT_ROOT / "data" / "json"


@app.get("/api/history")
async def list_history() -> list[dict]:
    """Return a list of past scrape result files (newest first)."""
    if not JSON_DIR.exists():
        return []
    files = sorted(JSON_DIR.glob("*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    results = []
    for f in files:
        stem = f.stem  # e.g. coffeshop_kudus-indonesia_20260306_130339
        parts = stem.split("_", 1)
        query = parts[0] if parts else stem
        location = parts[1].rsplit("_", 2)[0] if len(parts) > 1 else ""
        results.append({
            "filename": f.name,
            "query": query.replace("-", " "),
            "location": location.replace("-", " "),
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
        })
    return results


@app.get("/api/history/{filename}")
async def get_history_file(filename: str) -> list[dict]:
    """Return the contents of a specific history JSON file."""
    import re as _re
    if not _re.match(r'^[\w\-]+\.json$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    filepath = JSON_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="History file not found.")
    import json as _json
    with open(filepath, "r", encoding="utf-8") as fh:
        return _json.load(fh)
