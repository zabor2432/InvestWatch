"""Database schema shared by all InvestWatch services.

The `migrations` service owns the schema (Alembic autogenerates from this metadata);
other services only read and write rows.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


TS = DateTime(timezone=True)


class Firm(Base):
    """One entry of a KNF register, KNF warning list or I-SCAN warning list."""

    __tablename__ = "firms"
    __table_args__ = (UniqueConstraint("registry_list", "name_norm"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    registry_list: Mapped[str] = mapped_column(String(64), index=True)  # enums.RegistryList
    kind: Mapped[str] = mapped_column(String(16), index=True)  # enums.FirmKind
    name: Mapped[str] = mapped_column(Text)
    name_norm: Mapped[str] = mapped_column(Text, index=True)
    other_names: Mapped[list[Any]] = mapped_column(default=list)  # trade / additional / former names
    domains: Mapped[list[Any]] = mapped_column(default=list)
    country: Mapped[str | None] = mapped_column(Text)
    listed_at: Mapped[str | None] = mapped_column(String(32))  # licence / notification / warning date as listed
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)  # full source entry
    source_url: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    removed_at: Mapped[datetime | None] = mapped_column(TS)  # no longer on the source page


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # = RQ job id
    task: Mapped[str] = mapped_column(String(32), index=True)  # enums.Task
    source: Mapped[str | None] = mapped_column(String(32), index=True)  # enums.Platform, None for registry_sync
    limit: Mapped[int | None] = mapped_column(Integer)  # max results per query
    trigger: Mapped[str] = mapped_column(String(16))  # enums.JobTrigger
    status: Mapped[str] = mapped_column(String(16), index=True)  # enums.JobStatus
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)
    queries_total: Mapped[int] = mapped_column(Integer, default=0)
    queries_done: Mapped[int] = mapped_column(Integer, default=0)
    posts_seen: Mapped[int] = mapped_column(Integer, default=0)
    posts_new: Mapped[int] = mapped_column(Integer, default=0)
    posts_changed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[Any]] = mapped_column(default=list)
    stats: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Post(Base):
    """A collected post / video / web page. Unique per (platform, external_id)."""

    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("platform", "external_id"),
        Index("ix_posts_published_at", "published_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)  # enums.Platform
    external_id: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(16))  # enums.MediaType
    author_handle: Mapped[str | None] = mapped_column(Text, index=True)
    author_display_name: Mapped[str | None] = mapped_column(Text)
    author_url: Mapped[str | None] = mapped_column(Text)
    author_followers: Mapped[int | None] = mapped_column(BigInteger)
    title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    transcript_status: Mapped[str] = mapped_column(String(16))  # enums.TranscriptStatus
    outbound_links: Mapped[list[Any]] = mapped_column(default=list)
    engagement: Mapped[dict[str, Any]] = mapped_column(default=dict)  # views, likes, comments, shares
    lang: Mapped[str | None] = mapped_column(String(8))
    published_at: Mapped[datetime | None] = mapped_column(TS)
    first_task: Mapped[str] = mapped_column(String(32))  # task that found the post first
    first_query: Mapped[str] = mapped_column(Text)
    first_job_id: Mapped[str | None] = mapped_column(ForeignKey("scrape_jobs.id", ondelete="SET NULL"))
    content_hash: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict[str, Any]] = mapped_column(default=dict)
    scraped_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    versions: Mapped[list["PostVersion"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    media: Mapped[list["Media"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    hits: Mapped[list["PostHit"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class PostVersion(Base):
    """Snapshot of a post's text, stored on first sight and whenever content_hash changes."""

    __tablename__ = "post_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    post: Mapped[Post] = relationship(back_populates="versions")


class PostHit(Base):
    """Which task + query found a post (a post can be found by many queries and both tasks)."""

    __tablename__ = "post_hits"
    __table_args__ = (UniqueConstraint("post_id", "task", "query"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    task: Mapped[str] = mapped_column(String(32), index=True)
    query: Mapped[str] = mapped_column(Text)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("scrape_jobs.id", ondelete="SET NULL"))
    first_seen_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    post: Mapped[Post] = relationship(back_populates="hits")


class Media(Base):
    """Image or video thumbnail stored in object storage (MinIO)."""

    __tablename__ = "media"
    __table_args__ = (UniqueConstraint("post_id", "source_url"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # enums.MediaKind
    source_url: Mapped[str] = mapped_column(Text)
    bucket: Mapped[str | None] = mapped_column(String(63))
    object_key: Mapped[str | None] = mapped_column(Text)  # None when the download failed
    content_type: Mapped[str | None] = mapped_column(String(128))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())

    post: Mapped[Post] = relationship(back_populates="media")
