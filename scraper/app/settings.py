from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _csv(value: object) -> object:
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str = ""
    redis_url: str = "redis://redis:6379/0"
    searxng_url: str = "http://searxng:8080"

    # object storage (MinIO, S3 API)
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = Field("", validation_alias="MINIO_ROOT_USER")
    s3_secret_key: str = Field("", validation_alias="MINIO_ROOT_PASSWORD")
    s3_bucket: str = "investwatch-media"
    # pipeline input bucket (our contract v2 landing zone): every scraped post is also written there, see app/landing.py
    pipeline_bucket: str = Field("investwatch", validation_alias="PIPELINE_S3_BUCKET")
    landing_sync: bool = True  # after every job, push new posts and versions to the pipeline bucket (never duplicates)
    s3_public_url: str = "http://localhost:9000"  # how the frontend reaches MinIO
    media_max_bytes: int = 10 * 1024 * 1024

    # scheduling (cron syntax, empty = disabled)
    scheduler_enabled: bool = True
    scrape_cron: str = "0 */6 * * *"
    registry_sync_cron: str = "0 3 * * *"
    scrape_sources: Annotated[list[str], NoDecode] = ["youtube", "telegram", "web", "reddit", "wykop", "substack"]

    # limits
    default_limit: int = 20  # results per query when the request body has no limit
    max_queries_per_run: int = 30  # per (source, task) job; queries rotate between runs
    since_days: int = 90
    request_delay_seconds: float = 1.5
    request_timeout_seconds: float = 20.0
    telegram_channels_per_query: int = 3
    substack_publications_per_query: int = 3
    job_timeout_seconds: int = 3 * 3600

    # anti-blocking
    proxy_list: Annotated[list[str], NoDecode] = []
    user_agents_file: Path = Path("config/user_agents.txt")

    # web collector
    playwright_enabled: bool = True

    # optional collectors (free keys); empty = collector skipped with a warning
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    wykop_app_key: str = ""
    wykop_app_secret: str = ""

    # registry
    registry_seed_dir: Path = Path("/srv/firm_registry")
    iscan_nca_ids: Annotated[list[str], NoDecode] = ["75"]  # 75 = KNF (Poland); 24 = CySEC
    iscan_months: int = 24
    knf_warning_sections: Annotated[list[str], NoDecode] = [
        "art. 178 ustawy o obrocie instrumentami finansowymi",
        "ustawy o funduszach inwestycyjnych",
        "art. 99 i art. 99a ustawy o ofercie publicznej",
    ]

    config_dir: Path = Path("config")
    log_level: str = "INFO"

    _split = field_validator(
        "scrape_sources", "proxy_list", "iscan_nca_ids", "knf_warning_sections", mode="before"
    )(_csv)


@lru_cache
def settings() -> Settings:
    return Settings()
