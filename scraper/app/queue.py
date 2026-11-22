"""RQ queue: every job (manual API call or cron) gets a scrape_jobs row and an RQ job with the same id."""

import uuid
from functools import lru_cache

from redis import Redis
from rq import Queue

from investwatch_common.db import session_scope
from investwatch_common.enums import JobStatus, JobTrigger, Task
from investwatch_common.models import ScrapeJob

from app.log import log
from app.settings import settings

QUEUE_NAME = "scraper"
SCRAPE_TASKS = (Task.REGISTRY_ADS, Task.FIRM_MARKETING, Task.SHADOW_ADVISORY)
# module 2 looks for the firms' own materials: their websites and their YouTube channels
TASK_SOURCES = {Task.FIRM_MARKETING: {"web", "youtube"}}


@lru_cache
def redis() -> Redis:
    return Redis.from_url(settings().redis_url)


def queue() -> Queue:
    return Queue(QUEUE_NAME, connection=redis(), default_timeout=settings().job_timeout_seconds)


def enqueue(task: Task, source: str | None, limit: int | None, trigger: JobTrigger) -> ScrapeJob:
    job_id = str(uuid.uuid4())
    if task == Task.REGISTRY_SYNC:
        source, limit = None, None
    else:
        limit = limit or settings().default_limit
    with session_scope() as db:
        job = ScrapeJob(id=job_id, task=task, source=source, limit=limit, trigger=trigger, status=JobStatus.QUEUED,
                        errors=[], stats={})
        db.add(job)
    queue().enqueue("app.jobs.run_job", job_id, job_id=job_id, description=f"{task}:{source or '-'}")
    log.info("job_enqueued", job_id=job_id, task=task, source=source, limit=limit, trigger=trigger)
    return job


def enqueue_run_all(limit: int | None, trigger: JobTrigger) -> list[ScrapeJob]:
    return [
        enqueue(task, source, limit, trigger)
        for source in settings().scrape_sources
        for task in SCRAPE_TASKS
        if task not in TASK_SOURCES or source in TASK_SOURCES[task]
    ]
