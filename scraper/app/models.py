"""Unified output of every collector."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from investwatch_common.enums import MediaKind, MediaType, Platform, TranscriptStatus


class RawMedia(BaseModel):
    url: str  # source URL; for screenshots a synthetic "screenshot:<viewport>:<sha>" id
    kind: MediaKind
    data: bytes | None = None  # already captured bytes (screenshots); otherwise `url` is downloaded
    content_type: str | None = None


class RawPost(BaseModel):
    platform: Platform
    external_id: str
    url: str
    media_type: MediaType = MediaType.TEXT
    author_handle: str | None = None
    author_display_name: str | None = None
    author_url: str | None = None
    author_followers: int | None = None
    title: str | None = None
    content: str | None = None
    transcript: str | None = None
    transcript_status: TranscriptStatus = TranscriptStatus.NOT_APPLICABLE
    outbound_links: list[str] = Field(default_factory=list)
    engagement: dict[str, int | None] = Field(default_factory=dict)
    published_at: datetime | None = None
    media: list[RawMedia] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)

    def text_for_lang(self) -> str:
        return "\n".join(x for x in (self.title, self.content, self.transcript) if x)
