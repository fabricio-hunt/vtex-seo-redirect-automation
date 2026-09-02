from dataclasses import dataclass

DEFAULT_XML_URL = "http://www.bemol.com.br/XMLData/googleshopping.xml"
DEFAULT_BASE_DOMAIN = "https://www.bemol.com.br"
DEFAULT_LEGACY_REDIRECT = "/superoferta"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class RecoveryConfig:
    """Tunable parameters for a URL recovery run. Defaults match the original hardcoded values."""

    xml_url: str = DEFAULT_XML_URL
    base_domain: str = DEFAULT_BASE_DOMAIN
    legacy_redirect: str = DEFAULT_LEGACY_REDIRECT
    threshold: int = 90
    check_http_status: bool = True
    max_workers: int = 10
    http_timeout: int = 10
    user_agent: str = DEFAULT_USER_AGENT

    def to_dict(self) -> dict:
        return {
            "xml_url": self.xml_url,
            "base_domain": self.base_domain,
            "legacy_redirect": self.legacy_redirect,
            "threshold": self.threshold,
            "check_http_status": self.check_http_status,
            "max_workers": self.max_workers,
            "http_timeout": self.http_timeout,
            "user_agent": self.user_agent,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecoveryConfig":
        return cls(**{**cls().to_dict(), **(data or {})})
