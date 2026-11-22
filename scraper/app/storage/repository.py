"""Persistence of collected posts: upsert, versioning, query hits and media."""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from investwatch_common.models import Media, Post, PostHit, PostVersion

from app.http import HttpClient
from app.models import RawPost
from app.storage.blobs import download_to_bucket, upload_bytes


@dataclass
class UpsertResult:
    post_id: int
    created: bool
    changed: bool


def content_hash(p: RawPost) -> str:
    text = "\x1f".join(x or "" for x in (p.title, p.content, p.transcript))
    return hashlib.sha256(text.encode()).hexdigest()


def _safe_key(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)[:120]


def upsert_post(
    db: Session, raw: RawPost, lang: str | None, task: str, query: str, job_id: str, http: HttpClient
) -> UpsertResult:
    now = datetime.now(UTC)
    post = db.scalar(select(Post).where(Post.platform == raw.platform, Post.external_id == raw.external_id))
    if post is not None and raw.transcript is None and post.transcript:
        # a later fetch without subtitles must not wipe the transcript we already have
        raw = raw.model_copy(update={"transcript": post.transcript, "transcript_status": post.transcript_status})
    digest = content_hash(raw)
    fields = dict(
        url=raw.url,
        media_type=raw.media_type,
        author_handle=raw.author_handle,
        author_display_name=raw.author_display_name,
        author_url=raw.author_url,
        author_followers=raw.author_followers,
        title=raw.title,
        content=raw.content,
        transcript=raw.transcript,
        transcript_status=raw.transcript_status,
        outbound_links=raw.outbound_links,
        engagement=raw.engagement,
        lang=lang,
        published_at=raw.published_at,
        raw=raw.raw,
    )
    if post is None:
        post = Post(
            platform=raw.platform, external_id=raw.external_id, first_task=task, first_query=query,
            first_job_id=job_id, content_hash=digest, scraped_at=now, last_seen_at=now, **fields,
        )
        db.add(post)
        db.flush()
        created = changed = True
    else:
        created, changed = False, post.content_hash != digest
        for k, v in fields.items():
            setattr(post, k, v)
        post.content_hash, post.last_seen_at = digest, now

    if changed:
        db.add(PostVersion(post_id=post.id, content_hash=post.content_hash, title=post.title,
                           content=post.content, transcript=post.transcript, captured_at=now))

    hit = db.scalar(select(PostHit).where(PostHit.post_id == post.id, PostHit.task == task, PostHit.query == query))
    if hit is None:
        db.add(PostHit(post_id=post.id, task=task, query=query, job_id=job_id, first_seen_at=now, last_seen_at=now))
    else:
        hit.last_seen_at, hit.job_id = now, job_id

    known = set(db.scalars(select(Media.source_url).where(Media.post_id == post.id)))
    for m in raw.media:
        if m.url in known:
            continue
        prefix = f"{raw.platform}/{_safe_key(raw.external_id)}"
        if m.data is not None:
            blob = upload_bytes(m.data, m.content_type or "application/octet-stream", prefix)
        else:
            blob = download_to_bucket(http, m.url, prefix)
        db.add(Media(
            post_id=post.id, kind=m.kind, source_url=m.url,
            bucket=blob.bucket if blob else None, object_key=blob.key if blob else None,
            content_type=blob.content_type if blob else None, size_bytes=blob.size if blob else None,
            sha256=blob.sha256 if blob else None,
        ))
        known.add(m.url)
    return UpsertResult(post.id, created, changed and not created)
