"""YouTube via yt-dlp: search (newest first), video metadata, thumbnail and Polish subtitles as transcript."""

import json
import re
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote_plus

import yt_dlp

from investwatch_common.enums import MediaKind, MediaType, Platform, TranscriptStatus

from app.collectors.base import Collector, extract_links
from app.log import log
from app.models import RawMedia, RawPost

RAW_KEYS = (
    "id", "title", "channel", "channel_id", "channel_url", "uploader_id", "uploader_url",
    "channel_follower_count", "view_count", "like_count", "comment_count", "duration", "timestamp",
    "upload_date", "tags", "categories", "language", "webpage_url", "thumbnail", "was_live", "media_type",
)
SUB_LANGS = ("pl", "pl-orig", "pl-PL")


class _YdlLogger:
    """Route yt-dlp output to structlog (keeps stdout JSON-only)."""

    def debug(self, msg: str) -> None:
        pass

    info = debug

    def warning(self, msg: str) -> None:
        log.debug("yt_dlp_warning", message=msg[:300])

    def error(self, msg: str) -> None:
        log.debug("yt_dlp_error", message=msg[:300])


def _vtt_to_text(vtt: str) -> str:
    lines: list[str] = []
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line or line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if not lines or lines[-1] != line:  # auto-captions repeat rolling lines
            lines.append(line)
    return " ".join(lines)


def _json3_to_text(raw: str) -> str:
    data = json.loads(raw)
    parts = []
    for ev in data.get("events", []):
        seg = "".join(s.get("utf8", "") for s in ev.get("segs", []) or [])
        if seg.strip():
            parts.append(seg.strip())
    return " ".join(parts)


class YouTubeCollector(Collector):
    platform = Platform.YOUTUBE

    def _ydl(self, **extra) -> yt_dlp.YoutubeDL:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "logger": _YdlLogger(),
            "skip_download": True,
            "noplaylist": True,
            "http_headers": {"User-Agent": self.http.random_ua(), "Accept-Language": "pl-PL,pl;q=0.9"},
            "socket_timeout": 20,
            "sleep_interval_requests": self.http.delay,
        }
        if proxy := self.http.proxy():
            opts["proxy"] = proxy
        opts.update(extra)
        return yt_dlp.YoutubeDL(opts)

    def search(self, query: str, limit: int) -> Iterator[RawPost]:
        # results page sorted by upload date (sp=CAI=); fetch extra entries because old videos are skipped
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp=CAI%3D"
        with self._ydl(extract_flat="in_playlist", playlistend=limit * 2) as ydl:
            found = ydl.extract_info(url, download=False) or {}
        ids = [e["id"] for e in found.get("entries") or [] if e and e.get("id")]
        emitted = 0
        for vid in ids:
            if emitted >= limit:
                break
            info, transcript = self._video(vid)
            if info is None:
                continue
            post = self._to_post(info, transcript)
            if self.too_old(post.published_at):
                continue
            emitted += 1
            yield post

    def _video(self, vid: str) -> tuple[dict | None, str | None]:
        """Metadata plus Polish subtitles. yt-dlp writes the subtitle files itself (a plain HTTP client
        gets 429 from the timedtext endpoint); the video is never downloaded."""
        url = f"https://www.youtube.com/watch?v={vid}"
        with tempfile.TemporaryDirectory() as tmp:
            subs = {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": list(SUB_LANGS),
                "subtitlesformat": "json3/vtt/best",
                "outtmpl": {"default": str(Path(tmp) / "%(id)s.%(ext)s")},
            }
            try:
                with self._ydl(**subs) as ydl:
                    info = ydl.extract_info(url, download=True)  # skip_download: subtitles only
            except yt_dlp.utils.DownloadError as exc:
                log.info("youtube_subtitles_failed", video_id=vid, error=str(exc)[:200])
                try:
                    with self._ydl() as ydl:
                        return ydl.extract_info(url, download=False), None
                except yt_dlp.utils.DownloadError as exc2:
                    log.warning("youtube_video_failed", video_id=vid, error=str(exc2)[:300])
                    return None, None
            return info, self._read_subtitles(Path(tmp))

    @staticmethod
    def _read_subtitles(folder: Path) -> str | None:
        files = sorted(folder.glob("*.json3")) + sorted(folder.glob("*.vtt"))
        for f in files:
            try:
                raw = f.read_text(encoding="utf-8")
                text = (_json3_to_text(raw) if f.suffix == ".json3" else _vtt_to_text(raw)).strip()
            except (ValueError, OSError):
                continue
            if text:
                return text
        return None

    def _to_post(self, info: dict, transcript: str | None) -> RawPost:
        ts = info.get("timestamp")
        published = datetime.fromtimestamp(ts, UTC) if ts else None
        if published is None and (d := info.get("upload_date")):
            published = datetime.strptime(d, "%Y%m%d").replace(tzinfo=UTC)
        handle = info.get("uploader_id") or info.get("channel_id")
        description = info.get("description")
        thumb = info.get("thumbnail")
        return RawPost(
            platform=self.platform,
            external_id=info["id"],
            url=info.get("webpage_url") or f"https://www.youtube.com/watch?v={info['id']}",
            media_type=MediaType.VIDEO,
            author_handle=handle,
            author_display_name=info.get("channel") or info.get("uploader"),
            author_url=info.get("channel_url") or info.get("uploader_url"),
            author_followers=info.get("channel_follower_count"),
            title=info.get("title"),
            content=description,
            transcript=transcript,
            transcript_status=TranscriptStatus.OK if transcript else TranscriptStatus.UNAVAILABLE,
            outbound_links=extract_links(description),
            engagement={
                "views": info.get("view_count"),
                "likes": info.get("like_count"),
                "comments": info.get("comment_count"),
            },
            published_at=published,
            media=[RawMedia(url=thumb, kind=MediaKind.THUMBNAIL)] if thumb else [],
            raw={k: info.get(k) for k in RAW_KEYS if info.get(k) is not None},
        )
