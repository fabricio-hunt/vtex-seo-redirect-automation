import logging
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd

from .config import RecoveryConfig
from .export import build_result_frames, write_outputs
from .feed import FeedIndex, download_and_parse_xml
from .http_check import check_urls_batch
from .matching import match_single_url

logger = logging.getLogger(__name__)

PHASE_MATCHING = "matching"
PHASE_HTTP_CHECK = "http_check"
PHASE_DONE = "done"


def load_input_urls(input_file: str) -> list:
    """Reads 404 URLs from a .csv or .xlsx spreadsheet."""
    if input_file.endswith(".xlsx"):
        df = pd.read_excel(input_file)
    else:
        df = pd.read_csv(input_file)
    url_col = "URL" if "URL" in df.columns else df.columns[0]
    return [str(u).strip() for u in df[url_col].tolist()]


def match_row(url_404: str, feed: FeedIndex, config: RecoveryConfig) -> dict:
    """Matches a 404 URL using the rule chain defined in core.matching."""
    return match_single_url(url_404, feed, config)


def count_match_types(results: list) -> dict:
    """Aggregates frequency count per match_type across a result set."""
    return dict(Counter(r.get("match_type", "") for r in results))


def process_404_list(input_file: str, output_file: str, config: RecoveryConfig = None, feed: FeedIndex = None):
    """Full synchronous pipeline: match, concurrent HTTP verify, and export CSVs."""
    config = config or RecoveryConfig()
    feed = feed if feed is not None else download_and_parse_xml(config.xml_url)

    logger.info("Processing 404 file: %s", input_file)
    urls = load_input_urls(input_file)
    results = [match_row(url, feed, config) for url in urls]

    if config.check_http_status:
        unique_to_urls = list({r["to"] for r in results if r["to"]})
        logger.info("Verificando status HTTP para %d URLs de destino...", len(unique_to_urls))
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
    return JobState(rows=list(rows))


def step_match_batch(state: JobState, feed: FeedIndex, config: RecoveryConfig, batch_size: int) -> JobState:
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
    assert state.phase == PHASE_DONE, f"finalize_job called in phase {state.phase}"
    return build_result_frames(state.results, config.check_http_status)


def job_progress(state: JobState) -> dict:
    return {
        "phase": state.phase,
        "rows_total": len(state.rows),
        "rows_matched": state.next_row_index,
        "urls_total": len(state.unique_to_urls),
        "urls_checked": state.next_url_index,
        "match_type_breakdown": count_match_types(state.results),
    }
