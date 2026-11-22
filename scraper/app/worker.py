"""RQ worker (python -m app.worker); also runs the cron scheduler when SCHEDULER_ENABLED=true."""

from rq import Worker

from app import scheduler
from app.log import configure, log
from app.queue import QUEUE_NAME, redis
from app.settings import settings
from app.storage.blobs import ensure_bucket


def main() -> None:
    s = settings()
    configure(s.log_level)
    ensure_bucket()
    if s.scheduler_enabled:
        scheduler.start()
    log.info("worker_started", queue=QUEUE_NAME, scheduler=s.scheduler_enabled, sources=s.scrape_sources)
    Worker([QUEUE_NAME], connection=redis()).work(with_scheduler=False, logging_level="WARNING")


if __name__ == "__main__":
    main()
