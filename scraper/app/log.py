import logging
import sys

import structlog


def configure(level: str = "INFO") -> None:
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s")
    for noisy in ("httpx", "httpcore", "botocore", "urllib3", "trafilatura", "rq.worker"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


log = structlog.get_logger()
