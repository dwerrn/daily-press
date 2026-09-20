from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, field_validator


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    url: str
    section: str

    @field_validator("url")
    @classmethod
    def url_must_use_https(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("source URL must use HTTPS")
        return value


class ContentItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    title: str
    url: str
    summary: str = ""
    published_at: datetime | None = None
    section: str = "top"

    @property
    def canonical_url(self) -> str:
        parsed = urlsplit(self.url)
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
        default_port = {"http": 80, "https": 443}.get(scheme)
        netloc = hostname
        if ":" in hostname:
            netloc = f"[{hostname}]"
        if port is not None and port != default_port:
            netloc = f"{netloc}:{port}"
        query = sorted(
            (
                (name, value)
                for name, value in parse_qsl(parsed.query, keep_blank_values=True)
                if not name.lower().startswith("utm_")
            ),
            key=lambda item: item[0],
        )
        return urlunsplit((scheme, netloc, parsed.path, urlencode(query, doseq=True), ""))
