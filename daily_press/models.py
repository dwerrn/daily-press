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
        if value != value.strip():
            raise ValueError("source URL must not contain surrounding whitespace")
        parsed = urlsplit(value)
        hostname = parsed.hostname
        try:
            parsed.port
        except ValueError as error:
            raise ValueError("source URL must contain a valid port") from error
        if parsed.scheme.lower() != "https" or not hostname or any(char.isspace() for char in hostname):
            raise ValueError("source URL must be a well-formed HTTPS URL")
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
