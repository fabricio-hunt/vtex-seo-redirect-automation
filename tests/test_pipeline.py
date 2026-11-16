import os

import pandas as pd

from core.config import MIN_MATCH_SCORE, RecoveryConfig
from core.feed import FeedIndex
from core.pipeline import (
    finalize_job,
    job_progress,
    match_row,
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
    slug_to_category={
        "smartphone-samsung-galaxy-s23": "/celulares-e-smartphones/smartphone",
        "smart-tv-lg-55-polegadas": "/tv-e-video/smart-tv",
    },
)

LEGACY_CATEGORY = "/tv-e-video/smart-tv"

SAMPLE_URLS = [
    "https://www.bemol.com.br/smart-tv-lg-50-polegadas-p444",  # Linx legacy -> category of a similar product
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
    assert result_df.iloc[0]["to"] == LEGACY_CATEGORY
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
    assert result_df.iloc[0]["to"] == LEGACY_CATEGORY


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
        LEGACY_CATEGORY,
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


def test_match_row_attaches_match_score_per_match_type():
    assert match_row(SAMPLE_URLS[0], SAMPLE_FEED, RecoveryConfig())["match_type"].startswith("Legacy_Category_")
    assert match_row(SAMPLE_URLS[1], SAMPLE_FEED, RecoveryConfig())["match_score"] == 100  # Exact_Slug
    fuzzy = match_row(SAMPLE_URLS[2], SAMPLE_FEED, RecoveryConfig())
    assert fuzzy["match_type"].startswith("Fuzzy_")
    assert fuzzy["match_score"] >= MIN_MATCH_SCORE
    assert match_row(SAMPLE_URLS[3], SAMPLE_FEED, RecoveryConfig())["match_score"] == 0  # No_Match


def test_requesting_a_threshold_below_the_floor_still_enforces_min_match_score(tmpdir):
    """Even a caller asking for a very permissive threshold cannot get a low-confidence
    match into the final diagnostic — RecoveryConfig clamps it, and build_result_frames
    double-checks match_score as a second line of defense."""
    feed = FeedIndex(
        active_urls=["https://www.bemol.com.br/produto-completamente-diferente/p"],
        slug_to_url={"produto-completamente-diferente": "https://www.bemol.com.br/produto-completamente-diferente/p"},
    )
    config = RecoveryConfig(threshold=0, check_http_status=False)
    assert config.threshold == MIN_MATCH_SCORE  # clamped on construction

    input_file = _write_csv(tmpdir, ["https://www.bemol.com.br/algo-sem-relacao/p"])
    output_file = str(tmpdir.join("output.csv"))
    process_404_list(input_file, output_file, config=config, feed=feed)

    final_df = pd.read_csv(output_file, sep=";")
    assert len(final_df) == 0


def test_final_csv_drops_duplicate_from_rows(tmpdir):
    """Two 404 URLs that normalize to the same `from` path (e.g. one with a tracking query
    string) must only produce one row in the final CSV — VTEX's import rejects a duplicate
    `from` outright, so shipping both would guarantee at least one import failure."""
    input_file = _write_csv(tmpdir, [
        "https://www.bemol.com.br/smart-tv-lg-50-polegadas-p444",
        "https://www.bemol.com.br/smart-tv-lg-50-polegadas-p444?utm_source=google",
    ])
    output_file = str(tmpdir.join("output.csv"))

    process_404_list(input_file, output_file, config=RecoveryConfig(check_http_status=False), feed=SAMPLE_FEED)

    final_df = pd.read_csv(output_file, sep=";")
    assert len(final_df) == 1
    assert final_df.iloc[0]["from"] == "/smart-tv-lg-50-polegadas-p444"

    review_df = pd.read_csv(output_file.replace(".csv", "_review.csv"), sep=";")
    assert len(review_df) == 2  # both rows are still visible in the audit trail


def test_fuzzy_match_rejects_different_product_variants():
    """Slugs that are textually close but disagree on a model/size/storage number must not
    be fuzzy-matched to each other (e.g. a 50" TV redirected to a 55" TV)."""
    feed = FeedIndex(
        active_urls=["https://www.bemol.com.br/smart-tv-lg-55-polegadas/p"],
        slug_to_url={"smart-tv-lg-55-polegadas": "https://www.bemol.com.br/smart-tv-lg-55-polegadas/p"},
    )
    config = RecoveryConfig(check_http_status=False)

    result = match_row("https://www.bemol.com.br/smart-tv-lg-50-polegadas/p", feed, config)

    assert result["match_type"] == "No_Match"
    assert result["to"] == ""
    assert result["match_score"] == 0


def test_legacy_linx_url_redirects_to_category_of_most_similar_product():
    result = match_row(
        "https://www.bemol.com.br/smartphone-samsung-galaxy-s23-128gb-preto-mp--p1118971?tsid=16",
        SAMPLE_FEED,
        RecoveryConfig(check_http_status=False),
    )

    assert result["to"] == "/celulares-e-smartphones/smartphone"
    assert result["match_type"].startswith("Legacy_Category_")
    assert result["match_score"] >= MIN_MATCH_SCORE


def test_legacy_linx_url_without_equivalent_category_gets_no_redirect(tmpdir):
    input_file = _write_csv(tmpdir, ["https://www.bemol.com.br/produto-antigo-sem-relacao-p444"])
    output_file = str(tmpdir.join("output.csv"))

    process_404_list(input_file, output_file, config=RecoveryConfig(check_http_status=False), feed=SAMPLE_FEED)

    assert len(pd.read_csv(output_file, sep=";")) == 0
    review_df = pd.read_csv(output_file.replace(".csv", "_review.csv"), sep=";", keep_default_na=False)
    assert review_df.iloc[0]["match_type"] == "Legacy_No_Category"
    assert review_df.iloc[0]["to"] == ""


def test_nothing_redirects_to_superoferta(tmpdir):
    input_file = _write_csv(tmpdir, SAMPLE_URLS + ["https://www.bemol.com.br/produto-antigo-p444"])
    output_file = str(tmpdir.join("output.csv"))

    process_404_list(input_file, output_file, config=RecoveryConfig(check_http_status=False), feed=SAMPLE_FEED)

    for path in (output_file, output_file.replace(".csv", "_review.csv")):
        with open(path, encoding="utf-8-sig") as handle:
            assert "superoferta" not in handle.read()


def test_wcs_legacy_auth_mapping():
    config = RecoveryConfig(check_http_status=False)
    res_logon = match_row("https://www.bemol.com.br/webapp/wcs/stores/servlet/Logon", SAMPLE_FEED, config)
    assert res_logon["to"] == "/login"
    assert res_logon["match_type"] == "Legacy_WCS_Auth"

    res_checkout = match_row("https://www.bemol.com.br/webapp/wcs/stores/servlet/AjaxOrderItemDisplayView", SAMPLE_FEED, config)
    assert res_checkout["to"] == "/checkout"
    assert res_checkout["match_type"] == "Legacy_WCS_Auth"


def test_typo_comma_in_category():
    config = RecoveryConfig(check_http_status=False)
    res = match_row("https://www.bemol.com.br/cama,-mesa-e-banho/toalha-de-mesa", SAMPLE_FEED, config)
    assert res["to"] == "/cama-mesa-e-banho/toalha-de-mesa"
    assert res["match_type"] == "URL_Typo_Fixed"


def test_brand_vendor_suffix_stripping():
    config = RecoveryConfig(check_http_status=False)
    res = match_row("https://www.bemol.com.br/pampers-prg-", SAMPLE_FEED, config)
    assert res["to"] == "/pampers"
    assert res["match_type"] == "Brand_Vendor_Suffix_Stripped"


def test_discontinued_product_category_fallback():
    config = RecoveryConfig(check_http_status=False)
    # A product that no longer exists in feed (fuzzy ratio 78 < 90), but shares words with active category
    res = match_row("https://www.bemol.com.br/smart-tv-lg-55-polegadas-linha-antiga/p", SAMPLE_FEED, config)
    assert res["to"] == "/tv-e-video/smart-tv"
    assert res["match_type"].startswith("Discontinued_Product_Category_")
