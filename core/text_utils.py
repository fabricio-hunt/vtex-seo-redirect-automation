import logging
from urllib.parse import unquote

logger = logging.getLogger(__name__)

# Explicit replacements for common encoding artifacts (UTF-8 bytes read as Latin-1)
_MOJIBAKE_REPLACEMENTS = {
    "Âº": "º", "Â°": "°", "Ã£": "ã", "Ã§": "ç", "Ã¡": "á",
    "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú", "Ã¢": "â",
    "Ãª": "ê", "Ã´": "ô", "Ãµ": "õ", "Ã": "í", "Â": "",
}


def clean_text(text: str) -> str:
    """Fixes common UTF-8-read-as-Latin-1 mojibake artifacts (e.g. 'Âº' -> 'º')."""
    text = unquote(text)
    for bad, good in _MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)

    if "Ã" in text or "Â" in text:
        try:
            text = text.encode("latin1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError) as exc:
            logger.debug("clean_text: fallback re-decode failed for %r: %s", text, exc)

    return text
