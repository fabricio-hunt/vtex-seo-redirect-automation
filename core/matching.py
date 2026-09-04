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


def numeric_tokens(slug: str) -> set:
    """Digit sequences found in a slug (model number, screen size, storage, etc.)."""
    return set(re.findall(r"\d+", slug or ""))


def is_same_product_variant(slug_a: str, slug_b: str) -> bool:
    """Rejects fuzzy matches between slugs that disagree on numeric tokens.

    Two slugs can be textually very close (e.g. 'smart-tv-lg-50-polegadas' vs
    'smart-tv-lg-55-polegadas', or 'iphone-13' vs 'iphone-14') while naming a
    different model/size/storage variant. A high text-similarity score alone is
    not enough evidence they're the same product, so this guard is applied on
    top of the fuzzy score before accepting a match.
    """
    return numeric_tokens(slug_a) == numeric_tokens(slug_b)
