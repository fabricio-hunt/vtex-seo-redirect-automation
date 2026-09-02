"""Stateless compute endpoints backing the web UI.

This function does the CPU/network-bound work (parsing the feed, fuzzy
matching, HTTP verification) in small, bounded steps. It holds no state of
its own: every request carries the current JobState and every response
carries the updated one. Persistence (Vercel Blob for files, Vercel KV for
job records) and orchestration across steps live in the Next.js backend
(see lib/pythonCompute.ts), which is what the browser actually talks to.

Kept deliberately separate from core/, which has no notion of "requests" —
this module is just a thin JSON-in/JSON-out wrapper around it.
"""

import base64
import io
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException

from core.config import RecoveryConfig
from core.export import build_result_frames
from core.feed import FeedIndex, download_and_parse_xml
from core.pipeline import (
    JobState,
    job_progress,
    load_input_urls,
    step_http_check_batch,
    step_match_batch,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="404 URL Recovery — compute API")


def require_internal_token(x_internal_token: Optional[str] = Header(default=None)) -> None:
    """These endpoints do real network I/O against production infra (the feed, live URLs)
    and are reachable directly (Next.js middleware does not cover Python functions), so they
    require the same shared secret the Next.js backend uses when calling them."""
    expected = os.environ.get("INTERNAL_API_TOKEN")
    if not expected:
        # Fail closed: an unset token means this deployment isn't configured for production use yet.
        raise HTTPException(status_code=503, detail="INTERNAL_API_TOKEN is not configured on the server.")
    if x_internal_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Internal-Token header.")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# --- request/response payloads -------------------------------------------------

def _config_from_payload(data: Optional[Dict[str, Any]]) -> RecoveryConfig:
    return RecoveryConfig.from_dict(data or {})


def _state_from_payload(data: Dict[str, Any]) -> JobState:
    return JobState.from_dict(data)


# --- endpoints -------------------------------------------------------------

@app.post("/api/compute/load-input", dependencies=[Depends(require_internal_token)])
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


@app.post("/api/compute/parse-feed", dependencies=[Depends(require_internal_token)])
def parse_feed(payload: Dict[str, Any]) -> dict:
    """Downloads and parses the Google Shopping XML feed. This is the slowest single step
    (feed is tens of MB) — the Next.js backend caches its result and only calls this again
    once the cache expires."""
    xml_url = payload.get("xml_url") or RecoveryConfig().xml_url
    try:
        feed = download_and_parse_xml(xml_url)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to download/parse feed from %s: %s", xml_url, exc)
        raise HTTPException(status_code=502, detail=f"Falha ao baixar/processar o feed: {exc}") from exc

    return {"slug_to_url": feed.slug_to_url, "active_url_count": len(feed.active_urls)}


@app.post("/api/compute/match-batch", dependencies=[Depends(require_internal_token)])
def match_batch(payload: Dict[str, Any]) -> dict:
    """Matches up to `batch_size` pending rows against the feed."""
    state = _state_from_payload(payload["state"])
    feed = FeedIndex(slug_to_url=payload["feed"]["slug_to_url"])
    config = _config_from_payload(payload.get("config"))
    batch_size = int(payload.get("batch_size", 100))

    state = step_match_batch(state, feed, config, batch_size)
    return {"state": state.to_dict(), "progress": job_progress(state)}


@app.post("/api/compute/http-check-batch", dependencies=[Depends(require_internal_token)])
def http_check_batch(payload: Dict[str, Any]) -> dict:
    """Verifies HTTP status for up to `batch_size` pending unique destination URLs."""
    state = _state_from_payload(payload["state"])
    config = _config_from_payload(payload.get("config"))
    batch_size = int(payload.get("batch_size", 50))

    state = step_http_check_batch(state, config, batch_size)
    return {"state": state.to_dict(), "progress": job_progress(state)}


@app.post("/api/compute/finalize", dependencies=[Depends(require_internal_token)])
def finalize(payload: Dict[str, Any]) -> dict:
    """Builds the two output CSVs (as text) once a job has reached the done phase."""
    state = _state_from_payload(payload["state"])
    config = _config_from_payload(payload.get("config"))

    if state.phase != "done":
        raise HTTPException(status_code=409, detail=f"Job is not finished yet (phase={state.phase}).")

    final_df, review_df = build_result_frames(state.results, config.check_http_status)

    def to_csv_text(df: pd.DataFrame) -> str:
        buf = io.StringIO()
        df.to_csv(buf, sep=";", index=False)
        # Leading BOM so Excel opens the file with correct accented characters, matching
        # the encoding='utf-8-sig' behaviour of the original script's direct-to-file writes.
        return "﻿" + buf.getvalue()

    match_counts: Dict[str, int] = {}
    for row in state.results:
        match_counts[row["match_type"]] = match_counts.get(row["match_type"], 0) + 1

    return {
        "redirects_csv": to_csv_text(final_df),
        "review_csv": to_csv_text(review_df),
        "stats": {
            "rows_total": len(state.rows),
            "valid_redirects": len(final_df),
            "match_type_breakdown": match_counts,
        },
    }
