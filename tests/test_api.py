import base64

import pytest
from fastapi.testclient import TestClient

import api.index
from core.feed import FeedIndex
from core.feed_cache import CachedFeed

SAMPLE_FEED = FeedIndex(
    slug_to_url={"produto-ativo": "https://www.bemol.com.br/produto-ativo/p"},
    slug_to_category={"produto-ativo": "/categoria/subcategoria"},
)


@pytest.fixture()
def client():
    return TestClient(api.index.app)


@pytest.fixture()
def cached_feed(monkeypatch):
    requested_urls = []

    def fake_load_feed(xml_url, cache_dir, ttl_seconds):
        requested_urls.append(xml_url)
        return CachedFeed(feed=SAMPLE_FEED, cached_at=1234.0)

    monkeypatch.setattr(api.index, "load_feed", fake_load_feed)
    return requested_urls


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_load_input_parses_uploaded_csv(client):
    csv_bytes = b"URL\nhttps://www.bemol.com.br/produto-1/p\nhttps://www.bemol.com.br/produto-2/p\n"
    content_b64 = base64.b64encode(csv_bytes).decode()

    response = client.post("/api/compute/load-input", json={"filename": "input.csv", "content_base64": content_b64})

    assert response.status_code == 200
    assert response.json()["rows"] == [
        "https://www.bemol.com.br/produto-1/p",
        "https://www.bemol.com.br/produto-2/p",
    ]


def test_load_input_rejects_unparseable_file(client):
    content_b64 = base64.b64encode(b"\x00\x01\x02not a spreadsheet").decode()
    response = client.post("/api/compute/load-input", json={"filename": "input.xlsx", "content_base64": content_b64})
    assert response.status_code == 400


def test_prepare_feed_reports_cached_feed(client, cached_feed):
    response = client.post("/api/compute/prepare-feed", json={"xml_url": "https://example.com/feed.xml"})

    assert response.status_code == 200
    assert response.json() == {"active_url_count": 1, "cached_at": 1234.0}
    assert cached_feed == ["https://example.com/feed.xml"]


def test_prepare_feed_surfaces_download_failure_as_502(client, monkeypatch):
    def failing_load_feed(xml_url, cache_dir, ttl_seconds):
        raise OSError("network down")

    monkeypatch.setattr(api.index, "load_feed", failing_load_feed)

    response = client.post("/api/compute/prepare-feed", json={})
    assert response.status_code == 502


def test_match_batch_and_finalize_round_trip(client, cached_feed):
    state = {
        "phase": "matching",
        "rows": [
            "https://www.bemol.com.br/produto-ativo/p",
            "https://www.bemol.com.br/produto-sumido/p",
            "https://www.bemol.com.br/produto-ativo-antigo-p123",
        ],
        "next_row_index": 0,
        "results": [],
        "unique_to_urls": [],
        "next_url_index": 0,
        "status_cache": {},
    }
    config = {"check_http_status": False}

    response = client.post("/api/compute/match-batch", json={"state": state, "config": config, "batch_size": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["progress"]["phase"] == "done"
    breakdown = body["progress"]["match_type_breakdown"]
    assert breakdown["Same_URL_Ignored"] == 1
    assert breakdown["No_Match"] == 1
    assert body["state"]["results"][2]["to"] == "/categoria/subcategoria"

    finalize_response = client.post("/api/compute/finalize", json={"state": body["state"], "config": config})
    assert finalize_response.status_code == 200
    payload = finalize_response.json()
    assert payload["stats"]["rows_total"] == 3
    assert payload["stats"]["valid_redirects"] == 1
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
    response = client.post("/api/compute/finalize", json={"state": state, "config": {}})
    assert response.status_code == 409
