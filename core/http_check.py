import logging
from concurrent.futures import ThreadPoolExecutor

import requests

logger = logging.getLogger(__name__)


def check_url_status(url_path: str, base_domain: str, user_agent: str, timeout: int, cache: dict):
    """Checks the HTTP status code for a URL or path, with caching in `cache`."""
    if not url_path:
        return None
    if url_path in cache:
        return cache[url_path]

    full_url = url_path if url_path.startswith("http") else (
        f"{base_domain}{url_path if url_path.startswith('/') else '/' + url_path}"
    )
    headers = {"User-Agent": user_agent}
    try:
        response = requests.get(full_url, headers=headers, stream=True, timeout=timeout, allow_redirects=True)
        status = response.status_code
        response.close()
    except requests.RequestException as exc:
        logger.warning("HTTP check failed for %s: %s", full_url, exc)
        status = None

    cache[url_path] = status
    return status


def check_urls_batch(url_paths, base_domain: str, user_agent: str, timeout: int, max_workers: int, cache: dict) -> dict:
    """Checks a batch of URLs concurrently, populating/reusing `cache`. Returns {url_path: status}."""
    to_check = [u for u in url_paths if u not in cache]
    if to_check:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(
                lambda u: check_url_status(u, base_domain, user_agent, timeout, cache),
                to_check,
            ))
    return {u: cache.get(u) for u in url_paths}
