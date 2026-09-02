import logging
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlparse

import pandas as pd

from .config import RecoveryConfig
from .export import build_result_frames, write_outputs
from .feed import FeedIndex, download_and_parse_xml, extract_slug
from .http_check import check_urls_batch
from .matching import is_linx_legacy, is_same_url
from .text_utils import clean_text

logger = logging.getLogger(__name__)


def load_input_urls(input_file: str) -> list:
    """Reads the 404 spreadsheet (.xlsx or .csv) and returns the list of URLs to recover."""
    if input_file.endswith(".xlsx"):
        df = pd.read_excel(input_file)
    else:
        df = pd.read_csv(input_file)
    url_col = "URL" if "URL" in df.columns else df.columns[0]
    return [str(u).strip() for u in df[url_col].tolist()]


def match_row(url_404: str, feed: FeedIndex, config: RecoveryConfig) -> dict:
    """Applies the matching rules (Legacy Linx -> Exact Slug -> Fuzzy Slug) to a single 404 URL.
    Does not perform HTTP verification; `status_code` is filled in afterwards."""
    url_404 = clean_text(str(url_404).strip())
    if not url_404.startswith("http"):
        url_404 = config.base_domain + (url_404 if url_404.startswith("/") else "/" + url_404)
    path_404 = urlparse(url_404).path

    def _result(dest_path: str, match_type: str) -> dict:
        if dest_path and is_same_url(path_404, dest_path):
            return {"from": path_404, "to": "", "type": "PERMANENT", "endDate": "", "match_type": "Same_URL_Ignored"}
        return {"from": path_404, "to": dest_path, "type": "PERMANENT", "endDate": "", "match_type": match_type}

    if is_linx_legacy(path_404):
        return _result(config.legacy_redirect, "Legacy_Linx")

    slug_404 = extract_slug(url_404)
    if slug_404 in feed.slug_to_url:
        dest_path = urlparse(clean_text(feed.slug_to_url[slug_404])).path
        return _result(dest_path, "Exact_Slug")

    if slug_404 and feed.slug_to_url:
        from rapidfuzz import fuzz, process

        match = process.extractOne(slug_404, list(feed.slug_to_url.keys()), scorer=fuzz.ratio)
        if match is not None:
            best_match, score = match[0], match[1]
            if score >= config.threshold:
                dest_path = urlparse(clean_text(feed.slug_to_url[best_match])).path
                return _result(dest_path, f"Fuzzy_{score}%")

    return {"from": path_404, "to": "", "type": "PERMANENT", "endDate": "", "match_type": "No_Match"}


def process_404_list(input_file: str, output_file: str, config: RecoveryConfig = None, feed: FeedIndex = None):
    """Full, synchronous pipeline (used by the CLI): matches every row, then verifies HTTP
    status of every unique destination, then writes redirects.csv + redirects_review.csv."""
    config = config or RecoveryConfig()
    feed = feed if feed is not None else download_and_parse_xml(config.xml_url)

    logger.info("Processing 404 file: %s", input_file)
    urls = load_input_urls(input_file)
    results = [match_row(url, feed, config) for url in urls]

    if config.check_http_status:
        unique_to_urls = list({r["to"] for r in results if r["to"]})
        logger.info("Verificando status HTTP para %d URLs de destino únicas...", len(unique_to_urls))
        status_by_url = check_urls_batch(
            unique_to_urls, config.base_domain, config.user_agent, config.http_timeout, config.max_workers, cache={},
        )
        for r in results:
            r["status_code"] = status_by_url.get(r["to"], "") if r["to"] else ""
    else:
        for r in results:
            r["status_code"] = 200 if r["to"] else ""

    final_df, review_df = build_result_frames(results, config.check_http_status)
    return write_outputs(final_df, review_df, output_file)


# ---------------------------------------------------------------------------
# Resumable / batched execution, for environments where a single invocation
# can't run the whole pipeline in one shot (e.g. short-timeout serverless
# functions). Each step processes a bounded amount of work and returns an
# updated, JSON-serializable JobState.
# ---------------------------------------------------------------------------

PHASE_MATCHING = "matching"
PHASE_HTTP_CHECK = "http_check"
PHASE_DONE = "done"


@dataclass
class JobState:
    phase: str = PHASE_MATCHING
    rows: list = field(default_factory=list)
    next_row_index: int = 0
    results: list = field(default_factory=list)
    unique_to_urls: list = field(default_factory=list)
    next_url_index: int = 0
    status_cache: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "rows": self.rows,
            "next_row_index": self.next_row_index,
            "results": self.results,
            "unique_to_urls": self.unique_to_urls,
            "next_url_index": self.next_url_index,
            "status_cache": self.status_cache,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JobState":
        return cls(**data)


def start_job(rows: list) -> JobState:
    """Creates the initial JobState for a list of 404 URLs (before any matching happens)."""
    return JobState(rows=list(rows))


def step_match_batch(state: JobState, feed: FeedIndex, config: RecoveryConfig, batch_size: int) -> JobState:
    """Matches up to `batch_size` pending rows. Advances to the http_check (or done) phase
    once every row has been matched."""
    assert state.phase == PHASE_MATCHING, f"step_match_batch called in phase {state.phase}"

    end = min(state.next_row_index + batch_size, len(state.rows))
    for i in range(state.next_row_index, end):
        state.results.append(match_row(state.rows[i], feed, config))
    state.next_row_index = end

    if state.next_row_index >= len(state.rows):
        if config.check_http_status:
            state.unique_to_urls = list({r["to"] for r in state.results if r["to"]})
            state.phase = PHASE_HTTP_CHECK
        else:
            for r in state.results:
                r["status_code"] = 200 if r["to"] else ""
            state.phase = PHASE_DONE

    return state


def step_http_check_batch(state: JobState, config: RecoveryConfig, batch_size: int) -> JobState:
    """Verifies HTTP status for up to `batch_size` pending unique destination URLs. Advances
    to the done phase (filling `status_code` on every result) once all have been checked."""
    assert state.phase == PHASE_HTTP_CHECK, f"step_http_check_batch called in phase {state.phase}"

    end = min(state.next_url_index + batch_size, len(state.unique_to_urls))
    batch = state.unique_to_urls[state.next_url_index:end]
    check_urls_batch(batch, config.base_domain, config.user_agent, config.http_timeout, config.max_workers, state.status_cache)
    state.next_url_index = end

    if state.next_url_index >= len(state.unique_to_urls):
        for r in state.results:
            r["status_code"] = state.status_cache.get(r["to"], "") if r["to"] else ""
        state.phase = PHASE_DONE

    return state


def finalize_job(state: JobState, config: RecoveryConfig):
    """Builds the final (redirects) and review DataFrames once a JobState reaches PHASE_DONE."""
    assert state.phase == PHASE_DONE, f"finalize_job called in phase {state.phase}"
    return build_result_frames(state.results, config.check_http_status)


def job_progress(state: JobState) -> dict:
    """A JSON-friendly progress/stats summary, suitable for a status-polling API response."""
    return {
        "phase": state.phase,
        "rows_total": len(state.rows),
        "rows_matched": state.next_row_index,
        "urls_total": len(state.unique_to_urls),
        "urls_checked": state.next_url_index,
        "match_type_breakdown": dict(Counter(r["match_type"] for r in state.results)),
    }
