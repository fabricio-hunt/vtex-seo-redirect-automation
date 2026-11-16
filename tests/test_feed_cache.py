import os

import pytest

from core import feed_cache
from core.feed import FeedIndex

XML_URL = "https://example.com/feed.xml"


@pytest.fixture(autouse=True)
def _clear_memory_cache():
    feed_cache.clear_memory_cache()
    yield
    feed_cache.clear_memory_cache()


def _counting_downloader(calls):
    def download(url):
        calls.append(url)
        return FeedIndex(
            slug_to_url={"produto": "https://www.bemol.com.br/produto/p"},
            slug_to_category={"produto": "/categoria"},
        )

    return download


def test_load_feed_downloads_once_then_reuses_disk_cache(tmp_path):
    calls = []
    first = feed_cache.load_feed(XML_URL, str(tmp_path), 3600, downloader=_counting_downloader(calls))
    assert calls == [XML_URL]
    assert first.feed.slug_to_category == {"produto": "/categoria"}

    # A fresh process (empty memory cache) must read the persisted copy instead of downloading.
    feed_cache.clear_memory_cache()
    second = feed_cache.load_feed(XML_URL, str(tmp_path), 3600, downloader=_counting_downloader(calls))
    assert calls == [XML_URL]
    assert second.feed.slug_to_url == first.feed.slug_to_url
    assert second.feed.slug_to_category == {"produto": "/categoria"}


def test_load_feed_redownloads_when_cache_is_stale(tmp_path):
    calls = []
    feed_cache.load_feed(XML_URL, str(tmp_path), 3600, downloader=_counting_downloader(calls))

    feed_cache.load_feed(XML_URL, str(tmp_path), 0, downloader=_counting_downloader(calls))

    assert calls == [XML_URL, XML_URL]
    assert not [name for name in os.listdir(tmp_path) if name.endswith(".tmp")]
