"""Wykop API v3 (free application key): search of entries ("wpisy") and links ("znaleziska")."""

from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

from investwatch_common.enums import MediaKind, MediaType, Platform

from app.collectors.base import Collector, CollectorUnavailable, extract_links
from app.log import log
from app.models import RawMedia, RawPost
from app.settings import settings

API = "https://wykop.pl/api/v3"
WARSAW = ZoneInfo("Europe/Warsaw")


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=WARSAW)
    except ValueError:
        return None


class WykopCollector(Collector):
    platform = Platform.WYKOP

    def __init__(self, http):
        super().__init__(http)
        self._token: str | None = None

    def check_available(self) -> None:
        s = settings()
        if not (s.wykop_app_key and s.wykop_app_secret):
            raise CollectorUnavailable("WYKOP_APP_KEY / WYKOP_APP_SECRET not set")

    def _headers(self) -> dict:
        if not self._token:
            s = settings()
            resp = self.http.post(f"{API}/auth", json={"data": {"key": s.wykop_app_key, "secret": s.wykop_app_secret}})
            resp.raise_for_status()
            self._token = resp.json()["data"]["token"]
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

    def search(self, query: str, limit: int) -> Iterator[RawPost]:
        half = max(1, limit // 2)
        yield from self._search("entries", query, limit - half)
        yield from self._search("links", query, half)

    def _search(self, kind: str, query: str, limit: int) -> Iterator[RawPost]:
        emitted, page = 0, 1
        while emitted < limit:
            resp = self.http.get(f"{API}/search/{kind}", params={"query": query, "page": page, "sort": "newest"},
                                 headers=self._headers())
            if resp.status_code != 200:
                log.warning("wykop_search_failed", kind=kind, status=resp.status_code, body=resp.text[:300])
                return
            items = resp.json().get("data") or []
            if not items:
                return
            for it in items:
                post = self._to_post(kind, it)
                if self.too_old(post.published_at):
                    continue
                yield post
                emitted += 1
                if emitted >= limit:
                    return
            page += 1

    def _to_post(self, kind: str, it: dict) -> RawPost:
        author = (it.get("author") or {}).get("username")
        media = it.get("media") or {}
        images: list[RawMedia] = []
        if (photo := media.get("photo") or {}).get("url"):
            images.append(RawMedia(url=photo["url"], kind=MediaKind.IMAGE))
        embed = media.get("embed") or {}
        is_video = embed.get("type") in {"video", "youtube"} if embed else False
        if is_video and embed.get("thumbnail"):
            images.append(RawMedia(url=embed["thumbnail"], kind=MediaKind.THUMBNAIL))
        content = it.get("content") if kind == "entries" else it.get("description")
        links = extract_links(content)
        source_url = (it.get("source") or {}).get("url")
        if source_url and source_url not in links:
            links.insert(0, source_url)
        if embed.get("url") and embed["url"] not in links:
            links.append(embed["url"])
        path = "wpis" if kind == "entries" else "link"
        slug = it.get("slug") or ""
        votes = it.get("votes") or {}
        return RawPost(
            platform=self.platform,
            external_id=f"{kind}:{it.get('id')}",
            url=f"https://wykop.pl/{path}/{it.get('id')}/{slug}".rstrip("/"),
            media_type=MediaType.VIDEO if is_video else MediaType.IMAGE if images else MediaType.TEXT,
            author_handle=author,
            author_display_name=author,
            author_url=f"https://wykop.pl/ludzie/{author}" if author else None,
            title=it.get("title"),
            content=content,
            outbound_links=links,
            engagement={"votes_up": votes.get("up"), "votes_down": votes.get("down"),
                        "comments": (it.get("comments") or {}).get("count")},
            published_at=_dt(it.get("published_at") or it.get("created_at")),
            media=images,
            raw={k: it.get(k) for k in ("id", "slug", "tags", "source", "hot", "adult", "created_at", "published_at")},
        )
