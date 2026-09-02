import logging
import os

import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_COLUMNS = ["from", "to", "type", "endDate"]


def build_result_frames(results: list, check_http_status: bool):
    """Splits raw match results into (final_df, review_df). final_df keeps only rows with
    a non-empty destination, that aren't a same-URL loop, and (if enabled) that returned HTTP 200."""
    out_df = pd.DataFrame(results)

    valid_mask = (
        (out_df["to"] != "")
        & (out_df["to"].notna())
        & (out_df["match_type"] != "Same_URL_Ignored")
    )
    if check_http_status:
        valid_mask = valid_mask & (out_df["status_code"].astype(str) == "200")

    final_df = out_df.loc[valid_mask, OUTPUT_COLUMNS]
    return final_df, out_df


def write_outputs(final_df: pd.DataFrame, review_df: pd.DataFrame, output_file: str):
    """Writes the VTEX import CSV and the full review CSV (utf-8-sig so Excel renders accents)."""
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    final_df.to_csv(output_file, sep=";", index=False, encoding="utf-8-sig")
    logger.info("Saved %d valid redirects (HTTP 200 & no same-URL loop) to %s", len(final_df), output_file)

    review_file = output_file.replace(".csv", "_review.csv")
    review_df.to_csv(review_file, sep=";", index=False, encoding="utf-8-sig")
    logger.info("Saved detailed review file to %s", review_file)

    return output_file, review_file
