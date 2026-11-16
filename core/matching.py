import re
from urllib.parse import urlparse

from rapidfuzz import fuzz, process

from .category import legacy_product_slug
from .feed import extract_slug
from .text_utils import clean_text

WCS_MAP = {
    "logon": "/login",
    "m20checkoutlogon": "/login",
    "changepassword": "/login",
    "personprocessservicepersonregisterwithcheckoutprofile": "/login",
    "personchangeservicepersonupdate": "/account",
    "logonform": "/login",
    "resetpassword": "/login",
    "m20userregistrationaddform": "/login",
    "relogonformview": "/login",
    "resetpasswordform": "/login",
    "userregistrationform": "/login",
    "ajaxorderitemdisplayview": "/checkout",
    "m20userregistrationupdate": "/account",
    "giftregistrylogondisplayview": "/login",
    "giftregistrycreateview": "/login",
    "giftregistryprofiledisplayview": "/login",
}

VENDOR_SUFFIX_RE = re.compile(r"-(prg|cty|fxc|fqm|r-b|cjh|sfy|cee|bar|m-o|op|aoi)-?$")
_P_18DIGIT_SUFFIX_RE = re.compile(r"-0{5,}\d+$")


def is_linx_legacy(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    return bool(re.search(r"-p\d+", url))


def is_same_url(path1: str, path2: str) -> bool:
    if not path1 or not path2:
        return False
    return path1.strip("/").lower() == path2.strip("/").lower()


def numeric_tokens(slug: str) -> set:
    return set(re.findall(r"\d+", slug or ""))


def is_same_product_variant(slug_a: str, slug_b: str) -> bool:
    """Rejects matches between slugs that disagree on numeric tokens (model/size/storage)."""
    return numeric_tokens(slug_a) == numeric_tokens(slug_b)


def match_single_url(url_404: str, feed, config) -> dict:
    """Matches a broken URL to an active product or category, enforcing loop protection."""
    url_404 = clean_text(str(url_404).strip())
    if not url_404.startswith("http"):
        url_404 = config.base_domain + (url_404 if url_404.startswith("/") else "/" + url_404)
    path_404 = urlparse(url_404).path

    def _result(dest_path: str, match_type: str, score: int) -> dict:
        if dest_path and is_same_url(path_404, dest_path):
            return {
                "from": path_404, "to": "", "type": "PERMANENT", "endDate": "",
                "match_type": "Same_URL_Ignored", "match_score": score,
            }
        return {
            "from": path_404, "to": dest_path, "type": "PERMANENT", "endDate": "",
            "match_type": match_type, "match_score": score,
        }

    # 1. Legacy Linx URL -> equivalent category
    if is_linx_legacy(path_404):
        legacy_slug = legacy_product_slug(path_404)
        if legacy_slug and feed.slug_to_category:
            category_path, score = feed.category_index.best_match(legacy_slug, config.threshold)
            if category_path:
                return _result(category_path, f"Legacy_Category_{score}%", score)
        return {
            "from": path_404, "to": "", "type": "PERMANENT", "endDate": "",
            "match_type": "Legacy_No_Category", "match_score": 0,
        }

    # 2. Legacy WCS store auth/account links
    if "/webapp/wcs/stores/servlet/" in path_404.lower():
        action = path_404.lower().split("/webapp/wcs/stores/servlet/")[-1].strip("/")
        if action in WCS_MAP:
            return _result(WCS_MAP[action], "Legacy_WCS_Auth", 100)

    # 3. Typo: comma in category path
    if ",-" in path_404:
        return _result(path_404.replace(",-", "-"), "URL_Typo_Fixed", 100)

    # 4. Brand vendor suffix: e.g. /pampers-prg- -> /pampers
    clean_p = path_404.strip("/")
    if VENDOR_SUFFIX_RE.search(clean_p):
        brand = VENDOR_SUFFIX_RE.sub("", clean_p)
        return _result(f"/{brand}", "Brand_Vendor_Suffix_Stripped", 100)

    # 5. Legacy /p/ prefix URLs: e.g. /p/tv-75-samsung-...-000000000000196155
    if path_404.startswith("/p/"):
        seg = _P_18DIGIT_SUFFIX_RE.sub("", path_404[3:].strip("/"))
        cat, score = feed.category_index.best_match(seg.lower(), threshold=config.threshold)
        if cat:
            return _result(cat, f"Legacy_P_Category_{score}%", score)

    # 6. Exact slug match
    slug_404 = extract_slug(url_404)
    if slug_404 in feed.slug_to_url:
        dest_path = urlparse(clean_text(feed.slug_to_url[slug_404])).path
        return _result(dest_path, "Exact_Slug", 100)

    # 7. Fuzzy slug match
    if slug_404 and feed.slug_to_url:
        match = process.extractOne(slug_404, list(feed.slug_to_url.keys()), scorer=fuzz.ratio)
        if match is not None:
            best_match, score = match[0], round(match[1])
            if score >= config.threshold and is_same_product_variant(slug_404, best_match):
                dest_path = urlparse(clean_text(feed.slug_to_url[best_match])).path
                return _result(dest_path, f"Fuzzy_{score}%", score)

    # 8. Discontinued VTEX /p product: fallback to equivalent category in feed
    if path_404.endswith("/p"):
        parts = path_404.strip("/").split("/")
        if len(parts) >= 2 and parts[-1] == "p":
            cat, score = feed.category_index.best_match(parts[-2].lower(), threshold=config.threshold)
            if cat:
                return _result(cat, f"Discontinued_Product_Category_{score}%", score)

    # 9. URLs ending with - (trailing dash without vendor suffix): e.g. /cama-carolina-
    if path_404.endswith("-"):
        base_slug = path_404.strip("-").strip("/")
        cat, score = feed.category_index.best_match(base_slug.lower(), threshold=config.threshold)
        if cat:
            return _result(cat, f"Category_Fuzzy_{score}%", score)

    return {"from": path_404, "to": "", "type": "PERMANENT", "endDate": "", "match_type": "No_Match", "match_score": 0}
