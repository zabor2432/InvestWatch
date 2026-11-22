import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from investwatch_common.enums import Platform

from app.http import HttpClient
from app.models import RawPost
from app.settings import settings

URL_RE = re.compile(r"https?://[^\s<>\"'()\[\]{}]+", re.IGNORECASE)


def extract_links(text: str | None) -> list[str]:
    out: list[str] = []
    for m in URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(".,;:!?")
        if u not in out:
            out.append(u)
    return out


class CollectorUnavailable(Exception):
    """Collector cannot run (missing key, not implemented). The job logs a warning and skips it."""


class Collector(ABC):
    platform: Platform
    capture_layout: bool = False  # module 2: also computed styles of text blocks (web); others ignore it

    def __init__(self, http: HttpClient):
        self.http = http
        self.since = datetime.now(UTC) - timedelta(days=settings().since_days)

    def check_available(self) -> None:  # noqa: B027 (optional hook, default: always available)
        """Raise CollectorUnavailable when the collector cannot run."""

    @abstractmethod
    def search(self, query: str, limit: int) -> Iterator[RawPost]:
        """Yield up to `limit` posts for `query`, newest first, not older than `self.since` where dated."""

    def too_old(self, published: datetime | None) -> bool:
        return published is not None and published < self.since

    def close(self) -> None:  # noqa: B027 (optional hook, default: nothing to release)
        """Release resources (browsers, sessions)."""
