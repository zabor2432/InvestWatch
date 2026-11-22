"""Client of the self-hosted SearXNG metasearch (JSON API) used for web and Telegram discovery."""

import time
from dataclasses import dataclass

from app.http import HttpClient
from app.log import log
from app.settings import settings


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    published: str | None
    engine: str | None


BLOCKED_RETRIES = 2  # upstream engines answer CAPTCHA / rate limits intermittently


def _page(http: HttpClient, base: str, query: str, page: int) -> dict | None:
    for attempt in range(BLOCKED_RETRIES + 1):
        resp = http.get(
            f"{base}/search",
            params={"q": query, "format": "json", "language": "pl", "pageno": page, "safesearch": 0},
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            log.warning("searxng_error", query=query, status=resp.status_code)
            return None
        data = resp.json()
        if data.get("results") or not data.get("unresponsive_engines") or attempt == BLOCKED_RETRIES:
            return data
        log.info("searxng_retry_blocked", query=query, engines=data["unresponsive_engines"], attempt=attempt + 1)
        time.sleep(5 * (attempt + 1))
    return None


def search(http: HttpClient, query: str, limit: int, pages: int = 3) -> list[SearchResult]:
    base = settings().searxng_url.rstrip("/")
    results: list[SearchResult] = []
    seen: set[str] = set()
    for page in range(1, pages + 1):
        data = _page(http, base, query, page)
        if data is None:
            break
        batch = data.get("results", [])
        for r in batch:
            url = r.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            results.append(SearchResult(url, r.get("title") or "", r.get("content") or "",
                                        r.get("publishedDate"), r.get("engine")))
            if len(results) >= limit:
                return results
        if not batch:
            if page == 1 and data.get("unresponsive_engines"):
                log.warning("searxng_engines_unresponsive", query=query, engines=data["unresponsive_engines"])
            break
    return results
