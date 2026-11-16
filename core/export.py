import io
import logging
import os

import pandas as pd

from .config import MIN_MATCH_SCORE

logger = logging.getLogger(__name__)

OUTPUT_COLUMNS = ["from", "to", "type", "endDate"]


def build_result_frames(results: list, check_http_status: bool):
    """Filters results by match confidence floor (MIN_MATCH_SCORE) and HTTP 200, deduplicating from paths."""
    out_df = pd.DataFrame(results)
    if out_df.empty:
        empty_df = pd.DataFrame(columns=OUTPUT_COLUMNS)
        return empty_df, out_df

    if "type" not in out_df.columns:
        out_df["type"] = "PERMANENT"
    if "endDate" not in out_df.columns:
        out_df["endDate"] = ""

    valid_mask = (
        (out_df["to"] != "")
        & (out_df["to"].notna())
        & (out_df["match_type"] != "Same_URL_Ignored")
        & (out_df["match_score"].fillna(0) >= MIN_MATCH_SCORE)
        & (out_df["from"].astype(str).str.strip("/").str.lower() != out_df["to"].astype(str).str.strip("/").str.lower())
    )
    if check_http_status:
        valid_mask = valid_mask & (out_df["status_code"].astype(str) == "200")

    final_df = out_df.loc[valid_mask, OUTPUT_COLUMNS].drop_duplicates(subset=["from"], keep="first")
    return final_df, out_df


def dataframe_to_vtex_csv(df: pd.DataFrame) -> str:
    """Serializes a DataFrame to CSV string formatted for VTEX import (UTF-8 BOM)."""
    buf = io.StringIO()
    df.to_csv(buf, sep=";", index=False)
    return "\ufeff" + buf.getvalue()


def write_outputs(final_df: pd.DataFrame, review_df: pd.DataFrame, output_file: str):
    """Writes the VTEX import CSV and the full review CSV in utf-8-sig."""
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    final_df.to_csv(output_file, sep=";", index=False, encoding="utf-8-sig")
    logger.info("Saved %d valid redirects to %s", len(final_df), output_file)

    review_file = output_file.replace(".csv", "_review.csv")
    review_df.to_csv(review_file, sep=";", index=False, encoding="utf-8-sig")
    logger.info("Saved detailed review file to %s", review_file)

    return output_file, review_file
