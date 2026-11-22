"""Reddit search through the official OAuth API (free "script" app, client-credentials grant)."""

import html
import time
from collections.abc import Iterator
from datetime import UTC, datetime

from investwatch_common.enums import MediaKind, MediaType, Platform

from app.collectors.base import Collector, CollectorUnavailable, extract_links
from app.models import RawMedia, RawPost
from app.settings import settings

API = "https://oauth.reddit.com"
UA = "investwatch-scraper/0.1 (research prototype)"


class RedditCollector(Collector):
    platform = Platform.REDDIT

    def __init__(self, http):
        super().__init__(http)
        self._token: str | None = None
        self._token_exp = 0.0

    def check_available(self) -> None:
        s = settings()
        if not (s.reddit_client_id and s.reddit_client_secret):
            raise CollectorUnavailable("REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set")

    def _auth(self) -> dict:
        if not self._token or time.time() > self._token_exp - 60:
            s = settings()
            resp = self.http.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(s.reddit_client_id, s.reddit_client_secret),
                headers={"User-Agent": UA},
            )
            resp.raise_for_status()
            data = resp.json()
            self._token, self._token_exp = data["access_token"], time.time() + data.get("expires_in", 3600)
        # Reddit requires a stable, descriptive User-Agent for API clients
        return {"Authorization": f"bearer {self._token}", "User-Agent": UA}

    def search(self, query: str, limit: int) -> Iterator[RawPost]:
        after = None
        emitted = 0
        while emitted < limit:
            params = {"q": query, "sort": "new", "t": "year", "limit": min(100, limit), "type": "link", "raw_json": 1}
            if after:
                params["after"] = after
            resp = self.http.get(f"{API}/search", params=params, headers=self._auth())
            resp.raise_for_status()
            listing = resp.json().get("data", {})
            children = listing.get("children", [])
            for child in children:
                post = self._to_post(child.get("data", {}))
                if self.too_old(post.published_at):
                    return  # sorted by new
                yield post
                emitted += 1
                if emitted >= limit:
                    return
            after = listing.get("after")
            if not after or not children:
                return

    def _to_post(self, d: dict) -> RawPost:
        published = datetime.fromtimestamp(d["created_utc"], UTC) if d.get("created_utc") else None
        links = extract_links(d.get("selftext"))
        if not d.get("is_self") and d.get("url") and d["url"] not in links:
            links.insert(0, d["url"])
        media: list[RawMedia] = []
        images = (d.get("preview") or {}).get("images") or []
        if images and (src := images[0].get("source", {}).get("url")):
            kind = MediaKind.THUMBNAIL if d.get("is_video") else MediaKind.IMAGE
            media.append(RawMedia(url=html.unescape(src), kind=kind))
        media_type = MediaType.VIDEO if d.get("is_video") else MediaType.IMAGE if media else MediaType.TEXT
        author = d.get("author")
        return RawPost(
            platform=self.platform,
            external_id=d.get("name") or f"t3_{d['id']}",
            url=f"https://www.reddit.com{d.get('permalink', '')}",
            media_type=media_type,
            author_handle=author,
            author_display_name=author,
            author_url=f"https://www.reddit.com/user/{author}" if author and author != "[deleted]" else None,
            title=d.get("title"),
            content=d.get("selftext") or None,
            outbound_links=links,
            engagement={"score": d.get("score"), "comments": d.get("num_comments")},
            published_at=published,
            media=media,
            raw={k: d.get(k) for k in ("id", "subreddit", "subreddit_subscribers", "link_flair_text", "domain",
                                       "url", "is_self", "is_video", "over_18", "upvote_ratio", "post_hint")},
        )
