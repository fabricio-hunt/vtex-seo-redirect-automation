import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import cached_property
from urllib.parse import urlparse

import requests

from .category import CategoryIndex, category_path_from_product_type
from .text_utils import clean_text

logger = logging.getLogger(__name__)

GOOGLE_SHOPPING_NAMESPACE = "{http://base.google.com/ns/1.0}"


def extract_slug(url: str) -> str:
    """Extracts the product slug from a Bemol product URL (.../<slug>/p)."""
    if not url or not isinstance(url, str):
        return ""
    try:
        url = clean_text(url)
        path = urlparse(url).path
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[-1] == "p":
            return parts[-2]
        return parts[0] if parts else ""
    except ValueError as exc:
        logger.debug("extract_slug: failed to parse %r: %s", url, exc)
        return ""


@dataclass
class FeedIndex:
    """Active URLs from the product feed, indexed by slug for matching.

    `slug_to_category` maps each product slug to its category page path (derived from
    `g:product_type`), used to redirect legacy Linx URLs to an equivalent category."""

    active_urls: list = field(default_factory=list)
    slug_to_url: dict = field(default_factory=dict)
    slug_to_category: dict = field(default_factory=dict)

    @cached_property
    def category_index(self) -> CategoryIndex:
        """Built lazily, once per feed, on the first legacy URL lookup."""
        return CategoryIndex(self.slug_to_category)


def parse_feed_xml(xml_source, max_items=None) -> FeedIndex:
    """Streams a Google Shopping XML feed (file-like object) into a FeedIndex."""
    index = FeedIndex()
    count = 0
    try:
        context = ET.iterparse(xml_source, events=("end",))
        for _, elem in context:
            namespace, _, tag_name = elem.tag.rpartition("}")
            if tag_name in ("entry", "item"):
                # `<link>` lives in the entry's own namespace (Atom for `<entry>`), which is
                # not necessarily the namespace of the first element seen (e.g. `g:*`).
                link_elem = elem.find(f"{namespace}}}link") if namespace else elem.find("link")
                if link_elem is not None and link_elem.text:
                    url = link_elem.text
                    index.active_urls.append(url)
                    slug = extract_slug(url)
                    if slug:
                        index.slug_to_url[slug] = url
                        product_type_elem = elem.find(f"{GOOGLE_SHOPPING_NAMESPACE}product_type")
                        category_path = category_path_from_product_type(
                            product_type_elem.text if product_type_elem is not None else ""
                        )
                        if category_path:
                            index.slug_to_category[slug] = category_path

                count += 1
                elem.clear()
                if max_items and count >= max_items:
                    break
    except ET.ParseError as exc:
        logger.error("Failed to parse feed XML after %d items: %s", count, exc)
        raise

    logger.info("Parsed %d active URLs from the feed.", len(index.active_urls))
    return index


def download_and_parse_xml(xml_url: str, max_items=None) -> FeedIndex:
    """Downloads the XML feed and extracts active URLs and slugs."""
    logger.info("Downloading XML feed from %s...", xml_url)
    try:
        response = requests.get(xml_url, stream=True, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Failed to download feed from %s: %s", xml_url, exc)
        raise

    response.raw.decode_content = True
    try:
        return parse_feed_xml(response.raw, max_items=max_items)
    finally:
        response.close()
