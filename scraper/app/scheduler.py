"""Cron-like scheduler (SCRAPE_CRON, REGISTRY_SYNC_CRON). Runs as a thread inside the worker container."""

import threading
from datetime import UTC, datetime

from croniter import croniter

from investwatch_common.enums import JobTrigger, Task

from app.log import log
from app.queue import enqueue, enqueue_run_all, redis
from app.settings import settings

LOCK_TTL = 120


def _fire(name: str) -> None:
    if name == "scrape":
        enqueue_run_all(None, JobTrigger.CRON)
    else:
        enqueue(Task.REGISTRY_SYNC, None, None, JobTrigger.CRON)


def loop(stop: threading.Event) -> None:
    s = settings()
    schedules = {n: c for n, c in (("scrape", s.scrape_cron), ("registry_sync", s.registry_sync_cron)) if c.strip()}
    if not schedules:
        log.info("scheduler_disabled", reason="no cron expressions")
        return
    nxt = {n: croniter(c, datetime.now(UTC)).get_next(datetime) for n, c in schedules.items()}
    log.info("scheduler_started", schedules=schedules, next_runs={n: t.isoformat() for n, t in nxt.items()})
    while not stop.is_set():
        now = datetime.now(UTC)
        for name, at in nxt.items():
            if now < at:
                continue
            # several workers may run the scheduler: only the one holding the lock enqueues
            if redis().set(f"investwatch:cron:{name}:{at.isoformat()}", "1", nx=True, ex=LOCK_TTL * 30):
                log.info("cron_fired", schedule=name, at=at.isoformat())
                try:
                    _fire(name)
                except Exception:
                    log.exception("cron_enqueue_failed", schedule=name)
            nxt[name] = croniter(schedules[name], now).get_next(datetime)
        stop.wait(15)


def start() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=loop, args=(stop,), name="scheduler", daemon=True).start()
    return stop

