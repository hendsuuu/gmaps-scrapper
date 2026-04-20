"""
Flask service that exposes the scraper to WSGI environments such as cPanel/Passenger.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import json
import logging
import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, request

# Utility imports (lightweight, always available)
try:
    from .utils import sanitise_text, setup_logging
except ImportError:
    from utils import sanitise_text, setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports for heavy scraper / exporter modules.
# Playwright may not be installed on all environments (e.g. cPanel shared
# hosting).  We defer the import so the Flask app can always start and
# serve lightweight endpoints (health-check, history, etc.).
# ---------------------------------------------------------------------------
_scraper_mod = None
_exporters_mod = None


def _get_scraper_mod():
    global _scraper_mod
    if _scraper_mod is None:
        try:
            from . import scraper as _mod
        except ImportError:
            import scraper as _mod
        _scraper_mod = _mod
    return _scraper_mod


def _get_exporters_mod():
    global _exporters_mod
    if _exporters_mod is None:
        try:
            from . import exporters as _mod
        except ImportError:
            import exporters as _mod
        _exporters_mod = _mod
    return _exporters_mod


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROXIES_FILE = PROJECT_ROOT / "proxies.txt"
JSON_DIR = PROJECT_ROOT / "data" / "json"

app = Flask(__name__)

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGIN",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]


jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


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


def set_job(job_id: str, **fields) -> None:
    with jobs_lock:
        jobs[job_id].update(fields)


def update_job_progress(job_id: str, payload: dict) -> None:
    with jobs_lock:
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


def get_job(job_id: str) -> dict | None:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return None
        return copy.deepcopy(job)


def prepare_record(record: dict, query: str, location: str) -> dict:
    prepared = dict(record)
    prepared["search_query"] = query
    prepared["search_location"] = location
    prepared["name"] = sanitise_text(prepared.get("name", ""))
    prepared["address"] = sanitise_text(prepared.get("address", ""))
    return prepared


def json_error(message: str, status_code: int):
    return jsonify({"detail": message}), status_code


def parse_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def validate_scrape_request(payload: dict | None) -> tuple[dict | None, tuple | None]:
    if not isinstance(payload, dict):
        return None, json_error("Request body must be a JSON object.", 400)

    query = str(payload.get("query", "")).strip()
    location = str(payload.get("location", "")).strip()
    language = str(payload.get("language", "en")).strip()
    headless = parse_bool(payload.get("headless", True), default=True)

    max_results_raw = payload.get("max_results", 20)
    try:
        max_results = int(max_results_raw)
    except (TypeError, ValueError):
        return None, json_error("Field 'max_results' must be an integer.", 400)

    if not query:
        return None, json_error("Field 'query' is required.", 400)
    if len(query) < 1 or len(query) > 120:
        return None, json_error("Field 'query' must be between 1 and 120 characters.", 400)

    if not location:
        return None, json_error("Field 'location' is required.", 400)
    if len(location) < 1 or len(location) > 160:
        return None, json_error("Field 'location' must be between 1 and 160 characters.", 400)

    if max_results < 1 or max_results > 120:
        return None, json_error("Field 'max_results' must be between 1 and 120.", 400)

    if len(language) < 2 or len(language) > 10:
        return None, json_error("Field 'language' must be between 2 and 10 characters.", 400)

    data = {
        "query": query,
        "location": location,
        "max_results": max_results,
        "headless": headless,
        "language": language,
    }
    return data, None


_scraper_pool: concurrent.futures.ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()


def _get_scraper_pool() -> concurrent.futures.ThreadPoolExecutor:
    """Lazily create the thread-pool so the module can be imported without
    spawning threads (important for Passenger cold-start)."""
    global _scraper_pool
    if _scraper_pool is None:
        with _pool_lock:
            if _scraper_pool is None:
                _scraper_pool = concurrent.futures.ThreadPoolExecutor(
                    max_workers=2,
                    thread_name_prefix="scraper",
                )
    return _scraper_pool


def run_scrape_job(job_id: str, scrape_request: dict) -> None:
    set_job(
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
        scraper_mod = _get_scraper_mod()
        exporters_mod = _get_exporters_mod()

        proxy_list = scraper_mod.load_proxies(str(PROXIES_FILE))
        scraper = scraper_mod.GoogleMapsScraper(
            max_results=scrape_request["max_results"],
            headless=scrape_request["headless"],
            language=scrape_request["language"],
            proxy_list=proxy_list,
        )

        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            leads = loop.run_until_complete(
                scraper.scrape(
                    query=scrape_request["query"],
                    location=scrape_request["location"],
                    progress_callback=lambda payload: update_job_progress(
                        job_id, payload),
                )
            )
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        records = [
            prepare_record(
                lead.to_dict(),
                scrape_request["query"],
                scrape_request["location"],
            )
            for lead in leads
        ]

        base_name = exporters_mod.build_base_name(
            scrape_request["query"],
            scrape_request["location"],
        )
        saved_files = exporters_mod.save_records(
            records, base_name, PROJECT_ROOT)
        latest_job = get_job(job_id) or {}
        latest_progress = latest_job.get("progress", {})
        processed = int(latest_progress.get("processed", len(records)))
        total = int(latest_progress.get("total", processed))

        set_job(
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
        set_job(
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


@app.before_request
def handle_preflight():
    """Handle CORS preflight (OPTIONS) requests globally."""
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        return response


@app.after_request
def apply_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin and origin in frontend_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "Access-Control-Request-Headers",
            "Content-Type, Authorization",
        )
    return response


@app.route("/", methods=["GET"])
def root():
    return jsonify({"message": "API is running"})


@app.route("/api/health", methods=["GET"])
def healthcheck():
    return jsonify(
        {
            "status": "ok",
            "service": "leads-scrapper-backend",
            "frontend_origins": frontend_origins,
        }
    )


@app.route("/api/scrape/jobs", methods=["POST"])
def create_scrape_job():
    payload, error_response = validate_scrape_request(
        request.get_json(silent=True))
    if error_response is not None:
        return error_response

    assert payload is not None
    job_id = uuid4().hex
    job = {
        "job_id": job_id,
        "status": "queued",
        "query": payload["query"],
        "location": payload["location"],
        "max_results": payload["max_results"],
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

    with jobs_lock:
        jobs[job_id] = job

    _get_scraper_pool().submit(run_scrape_job, job_id, payload)
    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/scrape/jobs/<job_id>", methods=["GET"])
def read_scrape_job(job_id: str):
    job = get_job(job_id)
    if job is None:
        return json_error("Scrape job not found.", 404)
    return jsonify(job)


@app.route("/api/history", methods=["GET"])
def list_history():
    if not JSON_DIR.exists():
        return jsonify([])

    files = sorted(
        JSON_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    results = []
    for file_path in files:
        stem = file_path.stem
        parts = stem.split("_", 1)
        query = parts[0] if parts else stem
        location = parts[1].rsplit("_", 2)[0] if len(parts) > 1 else ""
        results.append(
            {
                "filename": file_path.name,
                "query": query.replace("-", " "),
                "location": location.replace("-", " "),
                "size": file_path.stat().st_size,
                "modified": datetime.fromtimestamp(
                    file_path.stat().st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
            }
        )
    return jsonify(results)


@app.route("/api/history/<filename>", methods=["GET"])
def get_history_file(filename: str):
    if not re.match(r"^[\w\-]+\.json$", filename):
        return json_error("Invalid filename.", 400)

    filepath = JSON_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        return json_error("History file not found.", 404)

    with open(filepath, "r", encoding="utf-8") as file_handle:
        return jsonify(json.load(file_handle))
