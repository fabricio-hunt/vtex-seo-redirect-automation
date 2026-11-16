"""Local feed cache: avoids re-downloading the (tens-of-MB) XML feed on every run.

The parsed feed index is kept in memory for the lifetime of the process and persisted as
JSON on disk, so it also survives restarts. A cached entry is reused until it is older than
`ttl_seconds`.
"""

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from .config import DEFAULT_FEED_CACHE_TTL_SECONDS
from .feed import FeedIndex, download_and_parse_xml

logger = logging.getLogger(__name__)


@dataclass
class CachedFeed:
    feed: FeedIndex
    cached_at: float


_memory_cache: Dict[str, CachedFeed] = {}
_lock = threading.Lock()


def _cache_file(cache_dir: str, xml_url: str) -> str:
    digest = hashlib.sha1(xml_url.encode("utf-8")).hexdigest()
    return os.path.join(cache_dir, f"feed-{digest}.json")


def _read_disk_cache(path: str) -> Optional[CachedFeed]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        feed = FeedIndex(
            active_urls=list(data["slug_to_url"].values()),
            slug_to_url=data["slug_to_url"],
            slug_to_category=data.get("slug_to_category", {}),
        )
        return CachedFeed(feed=feed, cached_at=float(data["cached_at"]))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError) as exc:
        logger.warning("Ignoring unreadable feed cache %s: %s", path, exc)
        return None


def _write_disk_cache(path: str, cached: CachedFeed) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "cached_at": cached.cached_at,
        "slug_to_url": cached.feed.slug_to_url,
        "slug_to_category": cached.feed.slug_to_category,
    }
    # Write-then-rename so a crash or a sync tool never leaves a half-written cache behind.
    tmp_path = f"{path}.{os.getpid()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(tmp_path, path)


def _is_fresh(cached: Optional[CachedFeed], ttl_seconds: float) -> bool:
    return cached is not None and (time.time() - cached.cached_at) < ttl_seconds


def load_feed(
    xml_url: str,
    cache_dir: str,
    ttl_seconds: float = DEFAULT_FEED_CACHE_TTL_SECONDS,
    downloader: Callable[[str], FeedIndex] = download_and_parse_xml,
) -> CachedFeed:
    """Returns the parsed feed for `xml_url`, from memory, then disk, then the network."""
    with _lock:
        cached = _memory_cache.get(xml_url)
        if _is_fresh(cached, ttl_seconds):
            return cached

        path = _cache_file(cache_dir, xml_url)
        cached = _read_disk_cache(path)
        if not _is_fresh(cached, ttl_seconds):
            logger.info("Feed cache missing or stale for %s, downloading...", xml_url)
            cached = CachedFeed(feed=downloader(xml_url), cached_at=time.time())
            _write_disk_cache(path, cached)

        _memory_cache[xml_url] = cached
        return cached


def clear_memory_cache() -> None:
    """Drops the in-process cache (used by tests)."""
    with _lock:
        _memory_cache.clear()
