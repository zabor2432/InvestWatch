"""Scraper HTTP API: manual job triggers and read-only views of jobs and collected posts."""

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from investwatch_common.db import session_scope
from investwatch_common.enums import JobTrigger, Platform, Task
from investwatch_common.models import Media, Post, PostHit, PostVersion, ScrapeJob

from app import landing
from app.log import configure
from app.queue import TASK_SOURCES, enqueue, enqueue_run_all
from app.settings import settings

configure(settings().log_level)
app = FastAPI(title="InvestWatch Scraper")


class JobRequest(BaseModel):
    task: Task
    source: Platform | None = Field(None, description="Required for registry_ads / firm_marketing / shadow_advisory")
    limit: int | None = Field(None, ge=1, le=500, description="Max results per query")

    @model_validator(mode="after")
    def _source_required(self):
        if self.task != Task.REGISTRY_SYNC and self.source is None:
            raise ValueError("source is required for scraping tasks")
        if self.task in TASK_SOURCES and self.source not in TASK_SOURCES[self.task]:
            raise ValueError(f"{self.task} supports sources: {', '.join(sorted(TASK_SOURCES[self.task]))}")
        return self


class RunAllRequest(BaseModel):
    limit: int | None = Field(None, ge=1, le=500)


class JobOut(BaseModel):
    id: str
    task: str
    source: str | None
    limit: int | None
    trigger: str
    status: str
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    queries_total: int
    queries_done: int
    posts_seen: int
    posts_new: int
    posts_changed: int
    errors: list[Any]
    stats: dict[str, Any]

    model_config = {"from_attributes": True}


class MediaOut(BaseModel):
    kind: str
    source_url: str
    url: str | None  # straight from MinIO (S3_PUBLIC_URL)
    api_url: str | None = None  # the same file through this API (/media/...), independent of the MinIO host port


class PostOut(BaseModel):
    id: int
    platform: str
    external_id: str
    url: str
    media_type: str
    author_handle: str | None
    author_display_name: str | None
    author_url: str | None
    author_followers: int | None
    title: str | None
    content: str | None
    transcript: str | None
    transcript_status: str
    outbound_links: list[Any]
    engagement: dict[str, Any]
    lang: str | None
    published_at: datetime | None
    scraped_at: datetime
    last_seen_at: datetime
    tasks: list[str]
    queries: list[str]
    media: list[MediaOut]


def _post_out(p: Post) -> PostOut:
    public = settings().s3_public_url.rstrip("/")
    return PostOut(
        **{k: getattr(p, k) for k in PostOut.model_fields if k not in {"tasks", "queries", "media"}},
        tasks=sorted({h.task for h in p.hits}),
        queries=sorted({h.query for h in p.hits}),
        media=[MediaOut(kind=m.kind, source_url=m.source_url,
                        url=f"{public}/{m.bucket}/{m.object_key}" if m.object_key else None,
                        api_url=f"/media/{m.object_key}" if m.object_key else None) for m in p.media],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", response_model=JobOut, status_code=202)
def create_job(req: JobRequest):
    job = enqueue(req.task, req.source.value if req.source else None, req.limit, JobTrigger.MANUAL)
    return _job(job.id)


@app.post("/jobs/run-all", response_model=list[JobOut], status_code=202)
def run_all(req: RunAllRequest | None = None):
    jobs = enqueue_run_all(req.limit if req else None, JobTrigger.MANUAL)
    return [_job(j.id) for j in jobs]


@app.post("/landing/sync")
def landing_sync() -> dict:
    """Write every scraped post to the pipeline bucket in contract v2 (idempotent: existing objects are skipped)."""
    return landing.sync()


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(limit: int = Query(50, ge=1, le=500)):
    with session_scope() as db:
        return list(db.scalars(select(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(limit)))


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str):
    return _job(job_id)


def _job(job_id: str) -> ScrapeJob:
    with session_scope() as db:
        job = db.get(ScrapeJob, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job


@app.get("/posts")
def list_posts(
    task: Task | None = None,
    source: Platform | None = None,
    since: datetime | None = Query(None, description="published_at (or scraped_at when undated) >= since"),
    text: str | None = Query(None, alias="q", description="text in title / content / url / author (case-insensitive)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    q = select(Post)
    if task:
        q = q.where(Post.id.in_(select(PostHit.post_id).where(PostHit.task == task)))
    if source:
        q = q.where(Post.platform == source)
    if since:
        q = q.where(func.coalesce(Post.published_at, Post.scraped_at) >= since)
    if text:
        like = f"%{text}%"
        q = q.where(Post.title.ilike(like) | Post.content.ilike(like) | Post.url.ilike(like)
                    | Post.author_display_name.ilike(like) | Post.author_handle.ilike(like))
    with session_scope() as db:
        total = db.scalar(select(func.count()).select_from(q.subquery()))
        rows = db.scalars(
            q.options(selectinload(Post.hits), selectinload(Post.media))
            .order_by(Post.scraped_at.desc()).limit(limit).offset(offset)
        ).all()
        return {"total": total, "items": [_post_out(p) for p in rows]}


@app.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: int):
    with session_scope() as db:
        p = db.get(Post, post_id, options=[selectinload(Post.hits), selectinload(Post.media)])
        if p is None:
            raise HTTPException(404, "post not found")
        return _post_out(p)


@app.get("/posts/{post_id}/details")
def post_details(post_id: int):
    """Everything stored for one post: fields, raw, hits (task / query / job), versions, media files."""
    public = settings().s3_public_url.rstrip("/")
    with session_scope() as db:
        p = db.get(Post, post_id, options=[selectinload(Post.hits), selectinload(Post.media)])
        if p is None:
            raise HTTPException(404, "post not found")
        versions = db.scalars(select(PostVersion).where(PostVersion.post_id == post_id)
                              .order_by(PostVersion.captured_at.desc())).all()
        return {
            **_post_out(p).model_dump(),
            "first_task": p.first_task, "first_query": p.first_query, "first_job_id": p.first_job_id,
            "content_hash": p.content_hash, "raw": p.raw,
            "hits": [{"task": h.task, "query": h.query, "job_id": h.job_id, "first_seen_at": h.first_seen_at,
                      "last_seen_at": h.last_seen_at} for h in sorted(p.hits, key=lambda h: h.first_seen_at)],
            "versions": [{"captured_at": v.captured_at, "content_hash": v.content_hash, "title": v.title,
                          "content_chars": len(v.content or ""), "transcript_chars": len(v.transcript or "")}
                         for v in versions],
            "media_files": [{"kind": m.kind, "source_url": m.source_url, "content_type": m.content_type,
                             "size_bytes": m.size_bytes, "created_at": m.created_at,
                             "url": f"{public}/{m.bucket}/{m.object_key}" if m.object_key else None,
                             "api_url": f"/media/{m.object_key}" if m.object_key else None}
                            for m in p.media],
        }


@app.get("/stats")
def stats():
    """Counts for the browser page: posts per task / platform, media per kind, jobs per status."""
    with session_scope() as db:
        def counts(stmt):
            return {k: v for k, v in db.execute(stmt).all()}

        return {
            "posts": db.scalar(select(func.count()).select_from(Post)),
            "by_task": counts(select(PostHit.task, func.count(func.distinct(PostHit.post_id))).group_by(PostHit.task)),
            "by_platform": counts(select(Post.platform, func.count()).group_by(Post.platform)),
            "media_by_kind": counts(select(Media.kind, func.count()).group_by(Media.kind)),
            "jobs_by_status": counts(select(ScrapeJob.status, func.count()).group_by(ScrapeJob.status)),
        }


@app.get("/browse", include_in_schema=False)
def browse():
    """Read-only HTML viewer of the collected data (posts, media from MinIO, jobs)."""
    return FileResponse(Path(__file__).parent / "static" / "browse.html", media_type="text/html")


@app.get("/media/{key:path}", include_in_schema=False)
def media(key: str):
    """A stored media file streamed from object storage (used by /browse; works whatever the MinIO host port)."""
    from botocore.exceptions import ClientError

    from app.storage.blobs import _s3

    try:
        obj = _s3().get_object(Bucket=settings().s3_bucket, Key=key)
    except ClientError:
        raise HTTPException(404, "media not found") from None
    return StreamingResponse(obj["Body"].iter_chunks(), media_type=obj.get("ContentType") or "application/octet-stream",
                             headers={"Cache-Control": "public, max-age=86400"})
