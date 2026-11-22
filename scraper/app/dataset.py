"""Export / import of the collected data, so a teammate can load it into their own containers.

    # export (writes <dir>/posts.jsonl, jobs.jsonl, manifest.json and media/<object key>)
    docker compose run --rm -v ./data:/data scraper python -m app.dataset export /data/scraped/<name>
    # import into your own db + MinIO (posts already present - same platform + external_id - are skipped)
    docker compose run --rm -v ./data:/data scraper python -m app.dataset import /data/scraped/<name>

Exported: scrape_jobs, posts with their post_hits, post_versions and media rows, and the media files themselves.
Not exported: the firm registry (`firms`) - every container rebuilds it with registry_sync / the seed files.
Database ids are not kept (posts get new ids on import); job ids (UUIDs) are kept so hits still point to their job.
"""

import argparse
import json
import mimetypes
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from investwatch_common.db import session_scope
from investwatch_common.models import Media, Post, PostHit, PostVersion, ScrapeJob

from app.log import configure, log
from app.settings import settings
from app.storage.blobs import _s3, ensure_bucket

POST_FIELDS = (
    "platform", "external_id", "url", "media_type", "author_handle", "author_display_name", "author_url",
    "author_followers", "title", "content", "transcript", "transcript_status", "outbound_links", "engagement", "lang",
    "published_at", "first_task", "first_query", "first_job_id", "content_hash", "raw", "scraped_at", "last_seen_at",
)
JOB_FIELDS = (
    "id", "task", "source", "limit", "trigger", "status", "created_at", "started_at", "finished_at", "queries_total",
    "queries_done", "posts_seen", "posts_new", "posts_changed", "errors", "stats",
)
DATES = {"published_at", "scraped_at", "last_seen_at", "created_at", "started_at", "finished_at", "first_seen_at",
         "captured_at"}


def _dump(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _load(row: dict) -> dict:
    return {k: (datetime.fromisoformat(v) if k in DATES and isinstance(v, str) else v) for k, v in row.items()}


def post_row(p: Post) -> dict:
    """A post (with hits, versions and media rows loaded) in the export shape; also the input of app.landing."""
    row = {k: _dump(getattr(p, k)) for k in POST_FIELDS}
    row["hits"] = [{"task": h.task, "query": h.query, "job_id": h.job_id,
                    "first_seen_at": _dump(h.first_seen_at), "last_seen_at": _dump(h.last_seen_at)} for h in p.hits]
    row["versions"] = [{"content_hash": v.content_hash, "title": v.title, "content": v.content,
                        "transcript": v.transcript, "captured_at": _dump(v.captured_at)} for v in p.versions]
    row["media"] = [{"kind": m.kind, "source_url": m.source_url, "object_key": m.object_key,
                     "content_type": m.content_type, "size_bytes": m.size_bytes, "sha256": m.sha256,
                     "created_at": _dump(m.created_at)} for m in p.media]
    return row


def export(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "media").mkdir(exist_ok=True)
    s3, bucket = _s3(), settings().s3_bucket
    n_posts = n_files = n_bytes = 0
    with session_scope() as db:
        jobs = db.scalars(select(ScrapeJob).order_by(ScrapeJob.created_at)).all()
        with open(out / "jobs.jsonl", "w") as fh:
            for j in jobs:
                fh.write(json.dumps({k: _dump(getattr(j, k)) for k in JOB_FIELDS}, ensure_ascii=False) + "\n")
        posts = db.scalars(select(Post).order_by(Post.id).options(
            selectinload(Post.hits), selectinload(Post.versions), selectinload(Post.media))).all()
        with open(out / "posts.jsonl", "w") as fh:
            for p in posts:
                row = post_row(p)
                for m in row["media"]:
                    if m["object_key"]:
                        target = out / "media" / m["object_key"]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            s3.download_file(bucket, m["object_key"], str(target))
                            n_files += 1
                            n_bytes += target.stat().st_size
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_posts += 1
    manifest = {
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"), "posts": n_posts, "jobs": len(jobs),
        "media_files": n_files, "media_bytes": n_bytes,
        "import": "docker compose run --rm -v ./data:/data scraper python -m app.dataset import /data/scraped/<name>",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    log.info("dataset_exported", dir=str(out), **{k: v for k, v in manifest.items() if k != "import"})
    return manifest


def import_(src: Path) -> dict:
    ensure_bucket()
    s3, bucket = _s3(), settings().s3_bucket
    stats = {"jobs": 0, "posts": 0, "posts_skipped": 0, "media_files": 0}
    with session_scope() as db:
        known_jobs = set(db.scalars(select(ScrapeJob.id)))
        for line in (src / "jobs.jsonl").read_text().splitlines():
            row = _load(json.loads(line))
            if row["id"] not in known_jobs:
                db.add(ScrapeJob(**row))
                known_jobs.add(row["id"])
                stats["jobs"] += 1
    for line in (src / "posts.jsonl").read_text().splitlines():
        row = _load(json.loads(line))
        hits, versions, media = row.pop("hits"), row.pop("versions"), row.pop("media")
        with session_scope() as db:
            if db.scalar(select(Post.id).where(Post.platform == row["platform"],
                                               Post.external_id == row["external_id"])):
                stats["posts_skipped"] += 1
                continue
            if row.get("first_job_id") not in known_jobs:
                row["first_job_id"] = None
            post = Post(**row)
            db.add(post)
            db.flush()
            for h in hits:
                h = _load(h)
                db.add(PostHit(post_id=post.id, **{**h, "job_id": h["job_id"] if h["job_id"] in known_jobs else None}))
            for v in versions:
                db.add(PostVersion(post_id=post.id, **_load(v)))
            for m in media:
                m = _load(m)
                key = m["object_key"]
                path = src / "media" / key if key else None
                if path and path.exists():
                    ctype = m["content_type"] or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                    s3.upload_file(str(path), bucket, key, ExtraArgs={"ContentType": ctype})
                    stats["media_files"] += 1
                else:
                    key = None  # file missing from the export: keep the row, without a file
                db.add(Media(post_id=post.id, kind=m["kind"], source_url=m["source_url"],
                             bucket=bucket if key else None, object_key=key, content_type=m["content_type"],
                             size_bytes=m["size_bytes"], sha256=m["sha256"], created_at=m["created_at"]))
            stats["posts"] += 1
    log.info("dataset_imported", dir=str(src), **stats)
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["export", "import"])
    p.add_argument("dir", type=Path)
    args = p.parse_args()
    configure(settings().log_level)
    result = export(args.dir) if args.action == "export" else import_(args.dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
