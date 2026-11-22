"""Substack newsletters (public JSON API, no key).

Substack's own search matches single words across languages, so - like Telegram channels - it is used to
discover publications: `substack.com/api/v1/top/search` returns posts and author profiles; Polish posts that contain
every word of the query are taken directly, and the publications of the matching authors / posts are then read
newest first through `<host>/api/v1/archive`, back to `since`. Full text comes from `<host>/api/v1/posts/<slug>`
(paid posts: only the free preview, `raw.audience = "only_paid"`). Every post also gets first-screen screenshots.
"""

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import quote, urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from investwatch_common.enums import MediaKind, MediaType, Platform
from investwatch_common.text import fold

from app.collectors import layout
from app.collectors.base import Collector, extract_links
from app.log import log
from app.models import RawMedia, RawPost
from app.settings import settings

API = "https://substack.com/api/v1"
ARCHIVE_PAGE = 12
RAW_KEYS = ("id", "publication_id", "slug", "type", "audience", "wordcount", "language", "post_date",
            "subtitle", "description", "postTags")


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"\w+", fold(text)) if len(w) >= 3]


class SubstackCollector(Collector):
    platform = Platform.SUBSTACK

    def __init__(self, http):
        super().__init__(http)
        self._pw = None
        self._browser = None
        self._profiles: dict[str, dict] = {}

    # ------------------------------------------------------------------ discovery

    def search(self, query: str, limit: int) -> Iterator[RawPost]:
        words = _words(query)
        direct, hosts = self._discover(query, words)
        if not direct and len(words) >= 3:
            # Substack matches any single word; retry with the leading word ("xtb kod promocyjny" -> the brand alias)
            direct, more = self._discover(words[0], words[:1])
            hosts += more
        hosts = list(dict.fromkeys(hosts))[: settings().substack_publications_per_query]
        log.info("substack_discovered", query=query, direct_posts=len(direct), publications=hosts)

        seen: set[str] = set()
        emitted = 0
        for post in direct:
            if emitted >= limit:
                return
            if (p := self._post(post, seen)) is not None:
                emitted += 1
                yield p
        per_pub = max(1, -(-(limit - emitted) // max(1, len(hosts))))
        for host in hosts:
            if emitted >= limit:
                return
            for post in self._archive(host, per_pub):
                if emitted >= limit:
                    return
                if (p := self._post(post, seen)) is not None:
                    emitted += 1
                    yield p

    def _discover(self, query: str, words: list[str]) -> tuple[list[dict], list[str]]:
        """Polish posts containing every query word (at least half of them for 3+ words), and the publications of
        those posts and of the matching author profiles."""
        data = self._json(f"{API}/top/search?query={quote(query)}&page=0") or {}
        need = len(words) if len(words) <= 2 else -(-len(words) // 2)
        direct: list[dict] = []
        hosts: list[str] = []
        for item in data.get("items") or []:
            if item.get("type") == "profileSearchResults":
                for r in item.get("results") or []:
                    if r.get("handle") and (host := self._profile_host(r["handle"])):
                        hosts.append(host)
            post, pub = item.get("post") or {}, item.get("publication") or {}
            if item.get("type") != "post" or not post.get("canonical_url"):
                continue
            if (post.get("language") or pub.get("language")) not in (None, "pl"):
                continue
            text = fold(" ".join(str(post.get(k) or "") for k in ("title", "subtitle", "truncated_body_text")))
            if sum(w in text for w in words) >= need:
                direct.append(post)
                hosts.append(urlparse(post["canonical_url"]).netloc)
        return direct, hosts

    def _json(self, url: str):
        try:
            resp = self.http.get(url, headers={"Accept": "application/json"})
        except Exception as exc:
            log.warning("substack_request_failed", url=url, error=str(exc)[:200])
            return None
        if resp.status_code != 200:
            log.info("substack_status", url=url, status=resp.status_code)
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    def _profile_host(self, handle: str) -> str | None:
        prof = self._profiles.get(handle)
        if prof is None:
            prof = self._json(f"{API}/user/{quote(handle)}/public_profile") or {}
            self._profiles[handle] = prof
        pub = prof.get("primaryPublication") or {}
        if pub.get("custom_domain"):
            return pub["custom_domain"]
        return f"{pub['subdomain']}.substack.com" if pub.get("subdomain") else None

    def _archive(self, host: str, limit: int) -> Iterator[dict]:
        """Newest posts of one publication, back to `since`."""
        emitted, offset = 0, 0
        while emitted < limit:
            url = f"https://{host}/api/v1/archive?sort=new&limit={ARCHIVE_PAGE}" + (f"&offset={offset}" if offset else "")
            batch = self._json(url)
            posts = batch if isinstance(batch, list) else (batch or {}).get("posts") or []
            if not posts:
                return
            for post in posts:
                if self.too_old(_dt(post.get("post_date"))):
                    return
                emitted += 1
                yield post
                if emitted >= limit:
                    return
            offset += len(posts)

    # ------------------------------------------------------------------ posts

    def _post(self, summary: dict, seen: set[str]) -> RawPost | None:
        url = summary.get("canonical_url")
        if not url or url in seen:
            return None
        seen.add(url)
        published = _dt(summary.get("post_date"))
        if self.too_old(published):
            return None
        host = urlparse(url).netloc
        full = self._json(f"https://{host}/api/v1/posts/{quote(summary.get('slug') or '')}") or summary
        html = full.get("body_html")
        text = HTMLParser(html).text(separator="\n", strip=True) if html else full.get("truncated_body_text")
        links: list[str] = []
        if html:
            for a in HTMLParser(html).css("a[href]"):
                href = a.attributes.get("href") or ""
                if href.startswith("http") and urlparse(href).netloc != host and href not in links:
                    links.append(href)
        for u in extract_links(text):
            if u not in links:
                links.append(u)
        byline = (full.get("publishedBylines") or summary.get("publishedBylines") or [{}])[0]
        prof = self._profiles.get(byline.get("handle") or "") or {}
        pub_name = ((byline.get("publicationUsers") or [{}])[0].get("publication") or {}).get("name")
        media: list[RawMedia] = []
        if cover := full.get("cover_image"):
            media.append(RawMedia(url=cover, kind=MediaKind.IMAGE))
        cap = self._capture(url)
        consent = cap.consent if cap else {}
        if cap:
            media += [RawMedia(url=layout.screenshot_id(vp, f"{full.get('title')}\x1f{text}"), kind=MediaKind.SCREENSHOT,
                               data=shot, content_type="image/png") for vp, shot in cap.screenshots]
        return RawPost(
            platform=self.platform,
            external_id=str(full.get("id") or summary.get("id") or url),
            url=url,
            media_type=MediaType.IMAGE if media else MediaType.TEXT,
            author_handle=byline.get("handle") or host,
            author_display_name=pub_name or byline.get("name") or host,
            author_url=f"https://{host}",
            author_followers=prof.get("subscriberCountNumber") or prof.get("followerCount"),
            title=full.get("title"),
            content="\n\n".join(x for x in (full.get("subtitle"), text) if x) or None,
            outbound_links=links,
            engagement={
                "likes": full.get("reaction_count") or sum((full.get("reactions") or {}).values()) or None,
                "comments": full.get("comment_count"),
                "shares": full.get("restacks"),
            },
            published_at=published,
            media=media,
            raw={**{k: full.get(k) for k in RAW_KEYS if full.get(k) is not None},
                 "author_name": byline.get("name"), "publication_name": pub_name, "host": host,
                 "full_text": bool(html), "consent": consent},
        )

    # ------------------------------------------------------------------ screenshots

    def _capture(self, url: str) -> layout.Capture | None:
        if not settings().playwright_enabled:
            return None
        try:
            if self._browser is None:
                from playwright.sync_api import sync_playwright

                self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.launch(args=["--no-sandbox"])
            return layout.capture(self._browser, url, self.http.random_ua())
        except Exception as exc:
            log.warning("layout_capture_failed", url=url, error=str(exc)[:300])
            return None

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
