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
    """Fixes common UTF-8-read-as-Latin-1 mojibake artifacts (e.g. 'Âº' -> 'º').

    Also fully resolves nested percent-encoding: some 404 reports (Google Search Console
    in particular) come back double-encoded, e.g. 'n%25C2%25B039' for 'n°39'. A single
    unquote() only partially resolves that, leaving a literal '%C2%B0' in the output —
    which VTEX's redirect import rejects outright. Looping until unquote() stops changing
    the string (capped so pathological input can't spin forever) fixes both single- and
    double-encoded input; already-decoded text is left untouched since unquote() is a no-op
    on it.
    """
    for _ in range(3):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded

    for bad, good in _MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)

    if "Ã" in text or "Â" in text:
        try:
            text = text.encode("latin1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError) as exc:
            logger.debug("clean_text: fallback re-decode failed for %r: %s", text, exc)

    return text
