import pandas as pd
from core.export import build_result_frames, dataframe_to_vtex_csv


def test_dataframe_to_vtex_csv_format():
    df = pd.DataFrame([
        {"from": "/origem-1", "to": "/destino-1", "type": "PERMANENT", "endDate": ""},
        {"from": "/origem-2", "to": "/destino-2", "type": "PERMANENT", "endDate": ""},
    ])
    csv_text = dataframe_to_vtex_csv(df)
    # Must start with UTF-8 BOM
    assert csv_text.startswith("\ufeff")
    # Must use semicolon delimiter
    assert "from;to;type;endDate\n" in csv_text.replace("\r\n", "\n")
    assert "/origem-1;/destino-1;PERMANENT;" in csv_text


def test_build_result_frames_filters_low_score_and_duplicates():
    results = [
        {"from": "/a", "to": "/b", "match_type": "Exact_Slug", "match_score": 100, "status_code": "200"},
        {"from": "/a", "to": "/b", "match_type": "Exact_Slug", "match_score": 100, "status_code": "200"},
        {"from": "/low", "to": "/c", "match_type": "Fuzzy_70%", "match_score": 70, "status_code": "200"},
        {"from": "/same", "to": "", "match_type": "Same_URL_Ignored", "match_score": 100, "status_code": "200"},
        {"from": "/err", "to": "/d", "match_type": "Exact_Slug", "match_score": 100, "status_code": "404"},
    ]
    final_df, review_df = build_result_frames(results, check_http_status=True)

    assert len(final_df) == 1
    assert final_df.iloc[0]["from"] == "/a"
    assert len(review_df) == 5

