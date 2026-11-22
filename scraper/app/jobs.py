"""Job bodies executed by the RQ worker."""

from datetime import UTC, datetime
from urllib.parse import urlparse

import structlog

from investwatch_common.db import session_scope
from investwatch_common.enums import JobStatus, Platform, Task
from investwatch_common.models import ScrapeJob

from app import landing
from app.collectors import COLLECTORS
from app.collectors.base import CollectorUnavailable
from app.http import HttpClient
from app.lang import is_polish
from app.log import log
from app.models import RawPost
from app.owners import published_by_registered_firm
from app.queries import m2_queries, queries_for_run
from app.queue import redis
from app.registry.sync import run_registry_sync
from app.relevance import investment_related
from app.settings import settings
from app.storage.repository import upsert_post

MAX_ERRORS = 50


def _update(job_id: str, **fields) -> None:
    with session_scope() as db:
        job = db.get(ScrapeJob, job_id)
        for k, v in fields.items():
            setattr(job, k, v)


def run_job(job_id: str) -> dict:
    with session_scope() as db:
        job = db.get(ScrapeJob, job_id)
        task, source, limit = Task(job.task), job.source, job.limit
    structlog.contextvars.bind_contextvars(job_id=job_id, task=task.value, source=source)
    _update(job_id, status=JobStatus.RUNNING, started_at=datetime.now(UTC))
    log.info("job_started", limit=limit)
    try:
        if task == Task.REGISTRY_SYNC:
            stats = run_registry_sync()
            _update(job_id, status=JobStatus.FINISHED, finished_at=datetime.now(UTC), stats=stats)
        else:
            stats = _scrape(job_id, task, Platform(source), limit)
            _hand_over()
        log.info("job_finished", stats=stats)
        return stats
    except Exception as exc:
        log.exception("job_failed")
        _update(job_id, status=JobStatus.FAILED, finished_at=datetime.now(UTC),
                errors=[{"error": f"{type(exc).__name__}: {exc}"[:1000]}])
        raise
    finally:
        structlog.contextvars.clear_contextvars()


def _hand_over() -> None:
    """New posts and versions go on to the pipeline bucket (contract v2). A failure here never fails the scrape job."""
    if not settings().landing_sync:
        return
    try:
        landing.sync()
    except Exception:
        log.exception("landing_failed")


def _owned_by_firm(platform: Platform, query: str, raw: RawPost) -> bool:
    """Module 2 keeps only content published by the firm itself (its own domain / its own channel)."""
    brand = m2_queries(platform.value).get(query)
    if brand is None:
        return False
    if platform == Platform.WEB:
        return brand.owns_host(urlparse(raw.url).netloc)
    if platform == Platform.YOUTUBE:
        return brand.owns_channel(raw.author_display_name, raw.author_handle)
    return False


def _scrape(job_id: str, task: Task, platform: Platform, limit: int) -> dict:
    http = HttpClient()
    collector = COLLECTORS[platform](http)
    # every web page gets first-screen screenshots; module 2 (rules 4-8, 13) also computed styles of text blocks
    collector.capture_layout = task == Task.FIRM_MARKETING
    counters = {"posts_seen": 0, "posts_new": 0, "posts_changed": 0}
    stats = {"skipped_language": 0, "skipped_not_owner": 0, "skipped_registered_owner": 0, "skipped_off_topic": 0,
             "per_query": {}}
    errors: list[dict] = []
    try:
        try:
            collector.check_available()
        except CollectorUnavailable as exc:
            log.warning("collector_unavailable", reason=str(exc))
            _update(job_id, status=JobStatus.FINISHED, finished_at=datetime.now(UTC),
                    errors=[{"warning": f"collector skipped: {exc}"}])
            return {"skipped": str(exc)}

        queries = queries_for_run(task, platform.value, redis())
        _update(job_id, queries_total=len(queries))
        for i, query in enumerate(queries, 1):
            found = 0
            try:
                for raw in collector.search(query, limit):
                    if task == Task.FIRM_MARKETING and not _owned_by_firm(platform, query, raw):
                        stats["skipped_not_owner"] += 1
                        continue
                    # modules 1 and 3 must not collect the registered firms' own pages / channels;
                    # module 3 also drops registered agents (they act for an authorised firm)
                    if task != Task.FIRM_MARKETING and published_by_registered_firm(
                        raw, agents=task == Task.SHADOW_ADVISORY
                    ):
                        stats["skipped_registered_owner"] += 1
                        continue
                    ok, lang = is_polish(raw.text_for_lang())
                    if not ok:
                        stats["skipped_language"] += 1
                        continue
                    on_topic, why = investment_related(raw)
                    if not on_topic:  # coupons, plain bank accounts, payment terminals...
                        stats["skipped_off_topic"] += 1
                        log.info("post_off_topic", url=raw.url, **why)
                        continue
                    with session_scope() as db:
                        res = upsert_post(db, raw, lang, task, query, job_id, http)
                    found += 1
                    counters["posts_seen"] += 1
                    counters["posts_new"] += res.created
                    counters["posts_changed"] += res.changed
            except Exception as exc:  # one failing query must not stop the job
                log.warning("query_failed", query=query, error=f"{type(exc).__name__}: {exc}"[:500])
                if len(errors) < MAX_ERRORS:
                    errors.append({"query": query, "error": f"{type(exc).__name__}: {exc}"[:500]})
            stats["per_query"][query] = found
            log.info("query_done", query=query, posts=found, progress=f"{i}/{len(queries)}")
            _update(job_id, queries_done=i, errors=errors, stats=stats, **counters)
        _update(job_id, status=JobStatus.FINISHED, finished_at=datetime.now(UTC))
        return {**counters, "skipped_language": stats["skipped_language"],
                "skipped_not_owner": stats["skipped_not_owner"],
                "skipped_registered_owner": stats["skipped_registered_owner"],
                "skipped_off_topic": stats["skipped_off_topic"], "errors": len(errors)}
    finally:
        collector.close()
        http.close()
