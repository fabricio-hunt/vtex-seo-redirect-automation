import os
from dataclasses import dataclass, fields

DEFAULT_XML_URL = "http://www.bemol.com.br/XMLData/googleshopping.xml"
DEFAULT_BASE_DOMAIN = "https://www.bemol.com.br"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Hard floor for match confidence: no row is allowed into the final diagnostic below this
# score, no matter what fuzzy `threshold` a caller (CLI flag, web UI, API payload) requests.
MIN_MATCH_SCORE = 80

DEFAULT_FEED_CACHE_TTL_SECONDS = 6 * 60 * 60


@dataclass
class RecoveryConfig:
    """Tunable parameters for a URL recovery run. Defaults match the original hardcoded values."""

    xml_url: str = DEFAULT_XML_URL
    base_domain: str = DEFAULT_BASE_DOMAIN
    threshold: int = 90
    check_http_status: bool = True
    max_workers: int = 10
    http_timeout: int = 10
    user_agent: str = DEFAULT_USER_AGENT

    def __post_init__(self) -> None:
        # Never let a caller-supplied threshold weaken the accuracy floor.
        if self.threshold < MIN_MATCH_SCORE:
            self.threshold = MIN_MATCH_SCORE

    def to_dict(self) -> dict:
        return {
            "xml_url": self.xml_url,
            "base_domain": self.base_domain,
            "threshold": self.threshold,
            "check_http_status": self.check_http_status,
            "max_workers": self.max_workers,
            "http_timeout": self.http_timeout,
            "user_agent": self.user_agent,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecoveryConfig":
        # Unknown keys are ignored so job records saved by older versions (e.g. with the
        # removed `legacy_redirect` field) still load.
        known_fields = {f.name for f in fields(cls)}
        overrides = {key: value for key, value in (data or {}).items() if key in known_fields}
        return cls(**{**cls().to_dict(), **overrides})


def local_data_dir() -> str:
    """Directory for local state (feed cache, jobs, result files). Shared with the Next.js app."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.environ.get("LOCAL_DATA_DIR") or os.path.join(repo_root, ".local-data")


def feed_cache_ttl_seconds() -> float:
    return float(os.environ.get("FEED_CACHE_TTL_SECONDS") or DEFAULT_FEED_CACHE_TTL_SECONDS)
