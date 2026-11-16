"""Local compute API backing the web UI.

Does the CPU/network-bound work (parsing the feed, fuzzy matching, HTTP verification) in
bounded steps so the UI can show progress. It holds no job state of its own: every request
carries the current JobState and every response carries the updated one. Job persistence
and orchestration across steps live in the Next.js app (see lib/pythonCompute.ts). The
parsed feed is cached in memory and on disk (core/feed_cache.py).

Meant to run only on the local machine, bound to 127.0.0.1 (see scripts/start-local.mjs).

Kept deliberately separate from core/, which has no notion of "requests" —
this module is just a thin JSON-in/JSON-out wrapper around it.
"""

import base64
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException

from core.config import RecoveryConfig, feed_cache_ttl_seconds, local_data_dir
from core.export import build_result_frames, dataframe_to_vtex_csv
from core.feed_cache import CachedFeed, load_feed
from core.pipeline import (
    JobState,
    count_match_types,
    job_progress,
    load_input_urls,
    step_http_check_batch,
    step_match_batch,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="404 URL Recovery — compute API")

# Captured once at process import time, not per-request. `--reload` has been observed to log
# "Reloading..." without actually respawning the worker (see KNOWN_ISSUES.md #2) — comparing
# these values across two /api/health calls is the fastest way to confirm a reload actually
# happened, without inspecting the process list.
_WORKER_STARTED_AT = datetime.now(timezone.utc).isoformat()
_WORKER_PID = os.getpid()


def _git_commit() -> Optional[str]:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:  # noqa: BLE001 - best-effort only, e.g. not a git checkout
        return None


_WORKER_GIT_COMMIT = _git_commit()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "pid": _WORKER_PID,
        "started_at": _WORKER_STARTED_AT,
        "git_commit": _WORKER_GIT_COMMIT,
    }


# --- request/response payloads -------------------------------------------------

def _config_from_payload(data: Optional[Dict[str, Any]]) -> RecoveryConfig:
    return RecoveryConfig.from_dict(data or {})


def _state_from_payload(data: Dict[str, Any]) -> JobState:
    return JobState.from_dict(data)


def _load_cached_feed(xml_url: Optional[str]) -> CachedFeed:
    url = xml_url or RecoveryConfig().xml_url
    try:
        return load_feed(url, os.path.join(local_data_dir(), "feed-cache"), feed_cache_ttl_seconds())
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a 502
        logger.error("Failed to download/parse feed from %s: %s", url, exc)
        raise HTTPException(status_code=502, detail=f"Falha ao baixar/processar o feed: {exc}") from exc


# --- endpoints -------------------------------------------------------------

@app.post("/api/compute/load-input")
def load_input(payload: Dict[str, Any]) -> dict:
    """Decodes an uploaded spreadsheet (.csv or .xlsx) and returns the list of 404 URLs."""
    filename = payload.get("filename", "input.csv")
    content_b64 = payload["content_base64"]
    suffix = ".xlsx" if filename.lower().endswith(".xlsx") else ".csv"

    raw = base64.b64decode(content_b64)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        rows = load_input_urls(tmp_path)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a 400
        logger.warning("Failed to parse uploaded spreadsheet %s: %s", filename, exc)
        raise HTTPException(status_code=400, detail=f"Não foi possível ler a planilha: {exc}") from exc
    finally:
        os.unlink(tmp_path)

    return {"rows": rows}


@app.post("/api/compute/prepare-feed")
def prepare_feed(payload: Dict[str, Any]) -> dict:
    """Downloads and parses the feed unless a fresh cached copy exists. This is the slowest
    single step (the feed is tens of MB), so the UI runs it on its own before matching."""
    cached = _load_cached_feed(payload.get("xml_url"))
    return {"active_url_count": len(cached.feed.slug_to_url), "cached_at": cached.cached_at}


@app.post("/api/compute/match-batch")
def match_batch(payload: Dict[str, Any]) -> dict:
    """Matches up to `batch_size` pending rows against the (cached) feed."""
    state = _state_from_payload(payload["state"])
    config = _config_from_payload(payload.get("config"))
    feed = _load_cached_feed(config.xml_url).feed
    batch_size = int(payload.get("batch_size", 100))

    state = step_match_batch(state, feed, config, batch_size)
    return {"state": state.to_dict(), "progress": job_progress(state)}


@app.post("/api/compute/http-check-batch")
def http_check_batch(payload: Dict[str, Any]) -> dict:
    """Verifies HTTP status for up to `batch_size` pending unique destination URLs."""
    state = _state_from_payload(payload["state"])
    config = _config_from_payload(payload.get("config"))
    batch_size = int(payload.get("batch_size", 50))

    state = step_http_check_batch(state, config, batch_size)
    return {"state": state.to_dict(), "progress": job_progress(state)}


@app.post("/api/compute/finalize")
def finalize(payload: Dict[str, Any]) -> dict:
    """Builds the two output CSVs (as text) once a job has reached the done phase."""
    state = _state_from_payload(payload["state"])
    config = _config_from_payload(payload.get("config"))

    if state.phase != "done":
        raise HTTPException(status_code=409, detail=f"Job is not finished yet (phase={state.phase}).")

    final_df, review_df = build_result_frames(state.results, config.check_http_status)

    return {
        "redirects_csv": dataframe_to_vtex_csv(final_df),
        "review_csv": dataframe_to_vtex_csv(review_df),
        "stats": {
            "rows_total": len(state.rows),
            "valid_redirects": len(final_df),
            "match_type_breakdown": count_match_types(state.results),
        },
    }
