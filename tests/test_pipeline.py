import os

import pandas as pd

from core.config import RecoveryConfig
from core.feed import FeedIndex
from core.pipeline import (
    finalize_job,
    job_progress,
    process_404_list,
    start_job,
    step_http_check_batch,
    step_match_batch,
)

SAMPLE_FEED = FeedIndex(
    active_urls=[
        "https://www.bemol.com.br/smartphone-samsung-galaxy-s23-novo/p",
        "https://www.bemol.com.br/smart-tv-lg-55-polegadas/p?idsku=999",
    ],
    slug_to_url={
        "smartphone-samsung-galaxy-s23": "https://www.bemol.com.br/smartphone-samsung-galaxy-s23-novo/p",
        "smart-tv-lg-55-polegadas": "https://www.bemol.com.br/smart-tv-lg-55-polegadas/p?idsku=999",
    },
)

SAMPLE_URLS = [
    "https://www.bemol.com.br/produto-antigo-p444",  # Linx legacy -> /superoferta
    "https://www.bemol.com.br/smartphone-samsung-galaxy-s23/p",  # Exact match
    "https://www.bemol.com.br/smart-tv-lg-55-polegada/p",  # Fuzzy match (missing 's')
    "https://www.bemol.com.br/produto-inexistente/p",  # No match -> filtered from final CSV
]


def _write_csv(tmpdir, urls):
    input_file = tmpdir.join("input.csv")
    pd.DataFrame({"URL": urls}).to_csv(input_file, index=False)
    return str(input_file)


def test_process_404_list_same_url_ignored(tmpdir):
    feed = FeedIndex(
        active_urls=["https://www.bemol.com.br/produto-teste/p"],
        slug_to_url={"produto-teste": "https://www.bemol.com.br/produto-teste/p"},
    )
    input_file = _write_csv(tmpdir, ["https://www.bemol.com.br/produto-teste/p"])
    output_file = str(tmpdir.join("output.csv"))

    process_404_list(input_file, output_file, config=RecoveryConfig(check_http_status=False), feed=feed)

    final_df = pd.read_csv(output_file, sep=";")
    assert len(final_df) == 0

    review_df = pd.read_csv(output_file.replace(".csv", "_review.csv"), sep=";")
    assert len(review_df) == 1
    assert review_df.iloc[0]["match_type"] == "Same_URL_Ignored"


def test_process_404_list_matches(tmpdir):
    input_file = _write_csv(tmpdir, SAMPLE_URLS)
    output_file = str(tmpdir.join("output.csv"))

    process_404_list(input_file, output_file, config=RecoveryConfig(check_http_status=False), feed=SAMPLE_FEED)

    assert os.path.exists(output_file)
    result_df = pd.read_csv(output_file, sep=";")

    # Only the 3 rows with a valid match make it to the final CSV (No_Match is excluded)
    assert len(result_df) == 3
    assert result_df.iloc[0]["to"] == "/superoferta"
    assert result_df.iloc[0]["type"] == "PERMANENT"
    assert result_df.iloc[1]["to"] == "/smartphone-samsung-galaxy-s23-novo/p"
    assert result_df.iloc[2]["to"] == "/smart-tv-lg-55-polegadas/p"

    review_df = pd.read_csv(output_file.replace(".csv", "_review.csv"), sep=";")
    assert len(review_df) == 4
    assert review_df.iloc[3]["match_type"] == "No_Match"


def test_process_404_list_reads_xlsx_input(tmpdir):
    input_file = str(tmpdir.join("input.xlsx"))
    pd.DataFrame({"URL": SAMPLE_URLS}).to_excel(input_file, index=False)
    output_file = str(tmpdir.join("output.csv"))

    process_404_list(input_file, output_file, config=RecoveryConfig(check_http_status=False), feed=SAMPLE_FEED)

    result_df = pd.read_csv(output_file, sep=";")
    assert len(result_df) == 3
    assert result_df.iloc[0]["to"] == "/superoferta"


def test_stepped_matching_produces_same_results_as_full_run():
    config = RecoveryConfig(check_http_status=False)

    state = start_job(SAMPLE_URLS)
    # Process in small batches to exercise the resumable path across multiple calls.
    while state.phase == "matching":
        state = step_match_batch(state, SAMPLE_FEED, config, batch_size=2)

    assert state.phase == "done"
    final_df, review_df = finalize_job(state, config)

    assert len(final_df) == 3
    assert list(final_df["to"]) == [
        "/superoferta",
        "/smartphone-samsung-galaxy-s23-novo/p",
        "/smart-tv-lg-55-polegadas/p",
    ]
    assert len(review_df) == 4


def test_stepped_http_check_advances_through_both_phases():
    config = RecoveryConfig(check_http_status=True, max_workers=2)

    state = start_job(SAMPLE_URLS[:3])  # skip the No_Match row, all 3 remaining resolve to a destination
    while state.phase == "matching":
        state = step_match_batch(state, SAMPLE_FEED, config, batch_size=1)

    assert state.phase == "http_check"
    assert len(state.unique_to_urls) == 3

    progress = job_progress(state)
    assert progress["rows_matched"] == 3
    assert progress["urls_checked"] == 0

    # Force deterministic status codes instead of hitting the network in tests.
    for url in state.unique_to_urls:
        state.status_cache[url] = 200

    while state.phase == "http_check":
        state = step_http_check_batch(state, config, batch_size=1)

    assert state.phase == "done"
    final_df, _ = finalize_job(state, config)
    assert len(final_df) == 3
    assert job_progress(state)["urls_checked"] == 3
