"""Category helpers used to redirect legacy Linx product URLs to an equivalent category page.

The Google Shopping feed exposes each product's category hierarchy in `g:product_type`
as `Level 1 - Level 2 - Level 3` (e.g. `Moda e Acessórios - Calçados - Tênis`). Slugifying
each level and joining them with `/` yields the store's real category URL
(`/moda-e-acessorios/calcados/tenis`).
"""

import re
import unicodedata
from urllib.parse import urlparse

PRODUCT_TYPE_LEVEL_SEPARATOR = " - "
_LEGACY_PRODUCT_ID_SUFFIX = re.compile(r"-+p\d+$")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def slugify_segment(text: str) -> str:
    """'Cama, Mesa e Banho' -> 'cama-mesa-e-banho' (accents stripped, dashes collapsed)."""
    if not text:
        return ""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return _NON_ALPHANUMERIC.sub("-", ascii_text.lower()).strip("-")


def category_path_from_product_type(product_type: str) -> str:
    """'Moda e Acessórios - Calçados - Tênis' -> '/moda-e-acessorios/calcados/tenis'."""
    if not product_type:
        return ""
    segments = [slugify_segment(level) for level in product_type.split(PRODUCT_TYPE_LEVEL_SEPARATOR)]
    segments = [segment for segment in segments if segment]
    return "/" + "/".join(segments) if segments else ""


def legacy_product_slug(url_or_path: str) -> str:
    """Extracts the product-name slug from a legacy Linx URL by dropping its `-p12345` id.

    '/tinta-acrilica-premium-mp--p1086695?v=1' -> 'tinta-acrilica-premium-mp'."""
    if not url_or_path:
        return ""
    path = urlparse(url_or_path).path.strip("/")
    last_segment = path.split("/")[-1] if path else ""
    return _LEGACY_PRODUCT_ID_SUFFIX.sub("", last_segment).strip("-")


# Words present in more than this share of products ("de", "com", "mp", ...) don't help to
# narrow down candidates, so they are not used to select which products get scored.
_COMMON_WORD_MAX_SHARE = 0.05


class CategoryIndex:
    """Finds the category of the active product most similar to a legacy product slug.

    Scoring every active product (100k+) for every legacy URL is slow, so an inverted word
    index first narrows the search to products sharing at least one distinctive word with
    the legacy slug; only those are scored with word-set similarity (order-insensitive).
    A product sharing only very common words can't reach a meaningful word-set score anyway.
    """

    def __init__(self, slug_to_category: dict):
        self._slugs = list(slug_to_category.keys())
        self._categories = [slug_to_category[slug] for slug in self._slugs]
        self._words = [slug.replace("-", " ") for slug in self._slugs]

        postings: dict = {}
        for position, words in enumerate(self._words):
            for word in set(words.split()):
                postings.setdefault(word, []).append(position)
        max_postings = max(1, int(len(self._slugs) * _COMMON_WORD_MAX_SHARE))
        self._postings = {word: ids for word, ids in postings.items() if len(ids) <= max_postings}

    def best_match(self, product_slug: str, threshold: int):
        """Returns (category_path, score); category_path is "" when nothing reaches `threshold`."""
        query = (product_slug or "").lower().replace("-", " ")
        candidate_ids = set()
        for word in set(query.split()):
            candidate_ids.update(self._postings.get(word, ()))
        if not candidate_ids:
            return "", 0

        from rapidfuzz import fuzz, process

        candidates = {position: self._words[position] for position in candidate_ids}
        match = process.extractOne(query, candidates, scorer=fuzz.token_set_ratio)
        if match is None:
            return "", 0
        _, score, best_position = match
        score = round(score)
        if score < threshold:
            return "", score
        return self._categories[best_position], score
