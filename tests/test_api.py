import base64

import pandas as pd
import pytest
from fastapi.testclient import TestClient

TOKEN = "test-secret"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", TOKEN)
    from api.index import app  # imported after the env var is set

    return TestClient(app)


def auth_headers():
    return {"X-Internal-Token": TOKEN}


def test_health_requires_no_auth(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_endpoint_rejects_missing_token(client):
    response = client.post("/api/compute/load-input", json={"filename": "x.csv", "content_base64": ""})
    assert response.status_code == 401


def test_load_input_parses_uploaded_csv(client):
    csv_bytes = b"URL\nhttps://www.bemol.com.br/produto-1/p\nhttps://www.bemol.com.br/produto-2/p\n"
    content_b64 = base64.b64encode(csv_bytes).decode()

    response = client.post(
        "/api/compute/load-input",
        json={"filename": "input.csv", "content_base64": content_b64},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["rows"] == [
        "https://www.bemol.com.br/produto-1/p",
        "https://www.bemol.com.br/produto-2/p",
    ]


def test_load_input_rejects_unparseable_file(client):
    content_b64 = base64.b64encode(b"\x00\x01\x02not a spreadsheet").decode()
    response = client.post(
        "/api/compute/load-input",
        json={"filename": "input.xlsx", "content_base64": content_b64},
        headers=auth_headers(),
    )
    assert response.status_code == 400


def test_match_batch_and_finalize_round_trip(client):
    feed = {
        "slug_to_url": {
            "produto-ativo": "https://www.bemol.com.br/produto-ativo/p",
        }
    }
    state = {
        "phase": "matching",
        "rows": ["https://www.bemol.com.br/produto-ativo/p", "https://www.bemol.com.br/produto-sumido/p"],
        "next_row_index": 0,
        "results": [],
        "unique_to_urls": [],
        "next_url_index": 0,
        "status_cache": {},
    }
    config = {"check_http_status": False}

    response = client.post(
        "/api/compute/match-batch",
        json={"state": state, "feed": feed, "config": config, "batch_size": 10},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["progress"]["phase"] == "done"
    assert body["progress"]["match_type_breakdown"] == {"Same_URL_Ignored": 1, "No_Match": 1}

    finalize_response = client.post(
        "/api/compute/finalize",
        json={"state": body["state"], "config": config},
        headers=auth_headers(),
    )
    assert finalize_response.status_code == 200
    payload = finalize_response.json()
    assert payload["stats"]["rows_total"] == 2
    assert payload["stats"]["valid_redirects"] == 0
    assert payload["redirects_csv"].startswith("﻿")


def test_finalize_rejects_unfinished_job(client):
    state = {
        "phase": "matching",
        "rows": ["a"],
        "next_row_index": 0,
        "results": [],
        "unique_to_urls": [],
        "next_url_index": 0,
        "status_cache": {},
    }
    response = client.post(
        "/api/compute/finalize",
        json={"state": state, "config": {}},
        headers=auth_headers(),
    )
    assert response.status_code == 409
