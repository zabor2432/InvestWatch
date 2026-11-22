"""Web pages found through SearXNG; main text extracted with trafilatura, Playwright as JS fallback."""

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse, urlunparse

import trafilatura
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from investwatch_common.enums import MediaKind, MediaType, Platform

from app.collectors import layout, searxng
from app.collectors.base import Collector
from app.log import log
from app.models import RawMedia, RawPost
from app.settings import settings

# handled by dedicated collectors or behind login walls
SKIP_HOSTS = (
    "youtube.com", "youtu.be", "t.me", "telegram.me", "reddit.com", "wykop.pl",
    "facebook.com", "instagram.com", "x.com", "twitter.com", "tiktok.com", "linkedin.com",
)
MIN_TEXT_CHARS = 200
MAX_LINKS = 200


def canonical(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme.lower(), p.netloc.lower().removeprefix("www."), p.path.rstrip("/") or "/", "", p.query, ""))


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value[:25], fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


class WebCollector(Collector):
    platform = Platform.WEB

    def __init__(self, http):
        super().__init__(http)
        self._pw = None
        self._browser = None

    def search(self, query: str, limit: int) -> Iterator[RawPost]:
        if query.startswith(("http://", "https://")):  # a page to fetch directly (module 2 firm pages)
            if post := self._fetch(searxng.SearchResult(url=query, title="", snippet="", published=None, engine=None)):
                yield post
            return
        hits = searxng.search(self.http, query, limit=limit * 2)
        emitted = 0
        for h in hits:
            if emitted >= limit:
                return
            host = _host(h.url)
            if any(host == s or host.endswith("." + s) for s in SKIP_HOSTS):
                continue
            post = self._fetch(h)
            if post:
                emitted += 1
                yield post

    def _get_browser(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
        return self._browser

    def _capture(self, url: str) -> layout.Capture | None:
        if not settings().playwright_enabled:
            return None
        try:
            return layout.capture(self._get_browser(), url, self.http.random_ua(), with_layout=self.capture_layout)
        except Exception as exc:
            log.warning("layout_capture_failed", url=url, error=str(exc)[:300])
            return None

    def _render(self, url: str) -> str | None:
        if not settings().playwright_enabled:
            return None
        try:
            page = self._get_browser().new_page(user_agent=self.http.random_ua(), locale="pl-PL")
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
                return page.content()
            finally:
                page.close()
        except Exception as exc:
            log.warning("playwright_failed", url=url, error=str(exc)[:300])
            return None

    def _fetch(self, hit: searxng.SearchResult) -> RawPost | None:
        try:
            resp = self.http.get(hit.url)
        except Exception as exc:
            log.warning("web_fetch_failed", url=hit.url, error=str(exc)[:200])
            resp = None
        ok = resp is not None and resp.status_code == 200 and "html" in resp.headers.get("content-type", "")
        if not ok:
            if resp is not None:
                log.info("web_skip", url=hit.url, status=resp.status_code, content_type=resp.headers.get("content-type"))
            # many sites refuse plain HTTP clients (403 / bot walls) but render in a browser
            if not ((cap := self._capture(hit.url)) and cap.html):
                return None
            final_url, html, doc = cap.final_url or hit.url, "", {}
        else:
            final_url = str(resp.url)
            html = resp.text
            doc = self._extract(html, final_url)
            cap = self._capture(final_url)  # every page: first-screen screenshots (desktop + mobile)
        rendered = False
        if cap and cap.html:  # the rendered page is the evidence, prefer its text when richer
            doc2 = self._extract(cap.html, final_url)
            if len(doc2.get("text") or "") > len(doc.get("text") or ""):
                html, doc, rendered = cap.html, doc2, True
        if len(doc.get("text") or "") < MIN_TEXT_CHARS and not cap and (html2 := self._render(final_url)):
            doc2 = self._extract(html2, final_url)
            if len(doc2.get("text") or "") > len(doc.get("text") or ""):
                html, doc, rendered = html2, doc2, True
        text = doc.get("text")
        if not text:
            return None
        tree = HTMLParser(html)
        host = _host(final_url)
        links: list[str] = []
        for a in tree.css("a[href]"):
            href = urljoin(final_url, a.attributes.get("href") or "")
            if href.startswith("http") and _host(href) != host and href not in links:
                links.append(href)
                if len(links) >= MAX_LINKS:
                    break
        og = tree.css_first('meta[property="og:image"]')
        image = urljoin(final_url, og.attributes.get("content") or "") if og and og.attributes.get("content") else None
        site = doc.get("sitename") or host
        media = [RawMedia(url=image, kind=MediaKind.IMAGE)] if image else []
        raw_extra = {}
        if cap:
            page_text = (doc.get("title") or "") + "\x1f" + text
            media += [RawMedia(url=layout.screenshot_id(vp, page_text), kind=MediaKind.SCREENSHOT, data=shot,
                               content_type="image/png") for vp, shot in cap.screenshots]
            if cap.layout:  # module 2 only
                raw_extra["layout"] = cap.layout
            raw_extra["consent"] = cap.consent
        return RawPost(
            platform=self.platform,
            external_id=hashlib.sha1(canonical(final_url).encode(), usedforsecurity=False).hexdigest(),
            url=final_url,
            media_type=MediaType.IMAGE if image else MediaType.TEXT,
            author_handle=host,
            author_display_name=doc.get("author") or site,
            author_url=f"{urlparse(final_url).scheme}://{urlparse(final_url).netloc}",
            title=doc.get("title") or hit.title,
            content=text,
            outbound_links=links,
            published_at=_parse_date(doc.get("date")) or _parse_date(hit.published),
            media=media,
            raw={
                **raw_extra,
                "search": {"title": hit.title, "snippet": hit.snippet, "engine": hit.engine, "url": hit.url},
                "metadata": {k: doc.get(k) for k in ("title", "author", "date", "sitename", "hostname", "categories", "tags", "description")},
                "rendered_with_playwright": rendered,
            },
        )

    @staticmethod
    def _extract(html: str, url: str) -> dict:
        out = trafilatura.extract(html, url=url, output_format="json", with_metadata=True, favor_recall=True)
        return json.loads(out) if out else {}

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
