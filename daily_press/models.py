from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict


class Source(BaseModel):
    name: str
    url: str
    section: str


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
        query = sorted(
            (name, value)
            for name, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not name.lower().startswith("utm_")
        )
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), "")
        )
