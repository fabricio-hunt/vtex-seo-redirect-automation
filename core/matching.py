import re


def is_linx_legacy(url: str) -> bool:
    """Checks if URL is a legacy Linx URL containing '-p12345'."""
    if not url or not isinstance(url, str):
        return False
    return bool(re.search(r"-p\d+", url))


def is_same_url(path1: str, path2: str) -> bool:
    """Checks if source path and target path point to the exact same URL."""
    if not path1 or not path2:
        return False
    return path1.strip("/").lower() == path2.strip("/").lower()
