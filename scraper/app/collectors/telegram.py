"""Telegram public channels.

Telegram has no public post search, so channels are discovered through SearXNG (`site:t.me <query>`)
and read through the public web preview `https://t.me/s/<channel>`, paging back to `since`.
"""

import math
import re
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser
from selectolax.lexbor import LexborNode as Node

from investwatch_common.enums import MediaKind, MediaType, Platform

from app.collectors import searxng
from app.collectors.base import Collector, extract_links
from app.lang import is_polish
from app.log import log
from app.models import RawMedia, RawPost
from app.settings import settings

RESERVED = {"s", "joinchat", "addstickers", "addemoji", "share", "proxy", "socks", "iv", "login", "c", "k", "a", "z"}
CHANNEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
BG_URL_RE = re.compile(r"background-image:\s*url\(['\"]?([^'\")]+)")


def channel_from_url(url: str) -> str | None:
    p = urlparse(url)
    if p.netloc.lower() not in {"t.me", "www.t.me", "telegram.me"}:
        return None
    parts = [x for x in p.path.split("/") if x]
    if parts and parts[0] == "s":
        parts = parts[1:]
    if not parts or parts[0].lower() in RESERVED or parts[0].startswith("+"):
        return None
    return parts[0] if CHANNEL_RE.match(parts[0]) else None


def parse_count(text: str | None) -> int | None:
    if not text:
        return None
    t = text.strip().replace(" ", "").replace(",", ".").upper()
    m = re.match(r"^([\d.]+)([KM]?)$", t)
    if not m:
        return None
    mult = {"": 1, "K": 1_000, "M": 1_000_000}[m.group(2)]
    return int(float(m.group(1)) * mult)


def _bg(node: Node | None) -> str | None:
    if node is None:
        return None
    m = BG_URL_RE.search(node.attributes.get("style") or "")
    return m.group(1) if m else None


class TelegramCollector(Collector):
    platform = Platform.TELEGRAM

    def search(self, query: str, limit: int) -> Iterator[RawPost]:
        hits = searxng.search(self.http, f"site:t.me {query}", limit=30)
        channels: list[str] = []
        for h in hits:
            ch = channel_from_url(h.url)
            if ch and ch.lower() not in {c.lower() for c in channels}:
                channels.append(ch)
        channels = channels[: settings().telegram_channels_per_query]
        if not channels:
            log.info("telegram_no_channels", query=query, search_hits=len(hits))
            return
        per_channel = max(1, math.ceil(limit / len(channels)))
        for ch in channels:
            yield from self._channel(ch, per_channel)

    def _channel(self, channel: str, limit: int) -> Iterator[RawPost]:
        before: int | None = None
        emitted = 0
        meta: dict = {}
        while emitted < limit:
            url = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
            resp = self.http.get(url)
            if resp.status_code != 200 or "tgme_channel_info" not in resp.text and "tgme_widget_message" not in resp.text:
                log.info("telegram_channel_unavailable", channel=channel, status=resp.status_code)
                return
            tree = HTMLParser(resp.text)
            if not meta:
                meta = self._channel_meta(tree, channel)
            msgs = tree.css("div.tgme_widget_message[data-post]")
            if not msgs:
                return
            posts = [self._to_post(m, meta) for m in msgs]
            posts = [p for p in posts if p is not None]
            if before is None and not self._polish_channel(channel, meta, posts):
                return
            # the page lists messages oldest -> newest
            for p in reversed(posts):
                if self.too_old(p.published_at):
                    return
                yield p
                emitted += 1
                if emitted >= limit:
                    return
            ids = [int(m.attributes["data-post"].rsplit("/", 1)[1]) for m in msgs]
            if before is not None and min(ids) >= before:
                return
            before = min(ids)
            if before <= 1:
                return

    @staticmethod
    def _polish_channel(channel: str, meta: dict, posts: list[RawPost]) -> bool:
        """Search hits for Polish queries include foreign channels (news, lotteries): judge the channel by its
        title, description and latest messages together and skip it unless they are Polish."""
        sample = "\n".join([meta.get("title") or "", meta.get("description") or "",
                            *[p.text_for_lang() for p in posts[-20:]]])
        ok, code = is_polish(sample)
        if not ok:
            log.info("telegram_channel_not_polish", channel=channel, lang=code)
        return ok

    def _channel_meta(self, tree: HTMLParser, channel: str) -> dict:
        title = tree.css_first(".tgme_channel_info_header_title")
        followers = None
        for counter in tree.css(".tgme_channel_info_counter"):
            ctype = counter.css_first(".counter_type")
            if ctype and ctype.text(strip=True) in {"subscribers", "subscriber", "members"}:
                followers = parse_count(counter.css_first(".counter_value").text(strip=True))
        desc = tree.css_first(".tgme_channel_info_description")
        return {
            "handle": channel,
            "title": title.text(strip=True) if title else channel,
            "followers": followers,
            "description": desc.text(separator="\n", strip=True) if desc else None,
        }

    def _to_post(self, m: Node, meta: dict) -> RawPost | None:
        data_post = m.attributes.get("data-post") or ""
        text_node = m.css_first(".tgme_widget_message_text")
        text = text_node.text(separator="\n", strip=True) if text_node else None
        links: list[str] = []
        if text_node:
            for a in text_node.css("a[href]"):
                href = a.attributes.get("href") or ""
                if href.startswith("http") and href not in links:
                    links.append(href)
        for u in extract_links(text):
            if u not in links:
                links.append(u)
        time_node = m.css_first(".tgme_widget_message_date time")
        published = None
        if time_node and (dt := time_node.attributes.get("datetime")):
            published = datetime.fromisoformat(dt)
        media: list[RawMedia] = []
        for ph in m.css("a.tgme_widget_message_photo_wrap"):
            if u := _bg(ph):
                media.append(RawMedia(url=u, kind=MediaKind.IMAGE))
        is_video = m.css_first(".tgme_widget_message_video_player, .tgme_widget_message_roundvideo_player") is not None
        if is_video and (u := _bg(m.css_first(".tgme_widget_message_video_thumb, .tgme_widget_message_roundvideo_thumb"))):
            media.append(RawMedia(url=u, kind=MediaKind.THUMBNAIL))
        if not text and not media:
            return None  # service message, sticker, poll without text
        views = m.css_first(".tgme_widget_message_views")
        owner = m.css_first(".tgme_widget_message_owner_name")
        fwd = m.css_first(".tgme_widget_message_forwarded_from_name")
        media_type = MediaType.VIDEO if is_video else MediaType.IMAGE if media else MediaType.TEXT
        return RawPost(
            platform=self.platform,
            external_id=data_post,
            url=f"https://t.me/{data_post}",
            media_type=media_type,
            author_handle=meta["handle"],
            author_display_name=owner.text(strip=True) if owner else meta["title"],
            author_url=f"https://t.me/{meta['handle']}",
            author_followers=meta["followers"],
            title=None,
            content=text,
            outbound_links=links,
            engagement={"views": parse_count(views.text(strip=True)) if views else None},
            published_at=published,
            media=media,
            raw={
                "channel": meta,
                "forwarded_from": fwd.text(strip=True) if fwd else None,
                "html": m.html[:20000] if m.html else None,
            },
        )
