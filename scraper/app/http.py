"""HTTP client with User-Agent rotation, optional proxy rotation, per-host delay and retries."""

import itertools
import random
import threading
import time
from urllib.parse import urlparse, urlunparse

import httpx

from app.log import log
from app.settings import settings

_FALLBACK_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
RETRY_STATUS = {429, 500, 502, 503, 504}


def _loggable(url: str) -> str:
    """URL without query string: signed URLs and API keys stay out of the logs."""
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc, p.path, "", "", ""))


def load_user_agents() -> list[str]:
    path = settings().user_agents_file
    try:
        uas = [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    except FileNotFoundError:
        uas = []
    return uas or [_FALLBACK_UA]


class HttpClient:
    def __init__(self, delay: float | None = None, retries: int = 3):
        s = settings()
        self.delay = s.request_delay_seconds if delay is None else delay
        self.retries = retries
        self.user_agents = load_user_agents()
        proxies = s.proxy_list or [None]
        self._clients = [
            httpx.Client(
                proxy=p,
                timeout=s.request_timeout_seconds,
                follow_redirects=True,
                http2=False,
            )
            for p in proxies
        ]
        self._rotation = itertools.cycle(self._clients)
        self._last_hit: dict[str, float] = {}
        self._lock = threading.Lock()

    def random_ua(self) -> str:
        return random.choice(self.user_agents)

    def proxy(self) -> str | None:
        """Next proxy for tools with their own HTTP stack (yt-dlp)."""
        s = settings()
        return random.choice(s.proxy_list) if s.proxy_list else None

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        with self._lock:
            wait = self._last_hit.get(host, 0) + self.delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_hit[host] = time.monotonic()

    def request(self, method: str, url: str, headers: dict | None = None, **kw) -> httpx.Response:
        hdrs = {
            "User-Agent": self.random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.6",
        }
        hdrs.update(headers or {})
        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            self._throttle(url)
            client = next(self._rotation)
            try:
                resp = client.request(method, url, headers=hdrs, **kw)
            except httpx.HTTPError as exc:  # network error, timeout
                last_exc = exc
                log.warning("http_error", url=_loggable(url), attempt=attempt, error=str(exc))
            else:
                if resp.status_code not in RETRY_STATUS:
                    return resp
                log.warning("http_retry_status", url=_loggable(url), attempt=attempt, status=resp.status_code)
                last_exc = httpx.HTTPStatusError(f"status {resp.status_code}", request=resp.request, response=resp)
                if attempt == self.retries:
                    return resp
            hdrs["User-Agent"] = self.random_ua()
            time.sleep(min(30, 2**attempt + random.random()))
        assert last_exc is not None  # noqa: S101 (narrowing for the type checker: the loop ran at least once)
        raise last_exc

    def get(self, url: str, **kw) -> httpx.Response:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> httpx.Response:
        return self.request("POST", url, **kw)

    def close(self) -> None:
        for c in self._clients:
            c.close()
