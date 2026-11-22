"""Hand-over of scraped posts to the pipeline bucket (app.landing): nothing is duplicated, failures never fail a job."""

import contextlib
import json
from pathlib import Path

import pytest

from app import jobs, landing
from app.settings import settings

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "scraped" / "2026-11-22"


class FakeS3:
    def __init__(self, media: dict[str, bytes] | None = None):
        self.objects: dict[str, bytes] = {}
        self.media = media or {}
        self.puts = 0

    def head_bucket(self, Bucket):  # noqa: N803
        return {}

    def get_object(self, Bucket, Key):  # noqa: N803
        data = self.media[Key]
        return {"Body": type("Body", (), {"read": lambda self: data})()}

    def put_object(self, Bucket, Key, Body, **kw):  # noqa: N803
        self.objects[Key] = Body
        self.puts += 1

    def get_paginator(self, name):
        s3 = self

        class Pages:
            def paginate(self, Bucket, Prefix):  # noqa: N803
                yield {"Contents": [{"Key": k} for k in s3.objects if k.startswith(Prefix)]}

        return Pages()


@pytest.fixture
def s3(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(landing, "_s3", lambda: fake)
    monkeypatch.setenv("PIPELINE_S3_BUCKET", "investwatch")
    monkeypatch.setenv("S3_BUCKET", "investwatch-media")
    settings.cache_clear()
    yield fake
    settings.cache_clear()


def test_from_export_writes_contract_objects_once_into_the_pipeline_bucket(s3):
    first = landing.from_export(str(SAMPLE))
    assert first["objects_new"] >= 17 and first["images_new"] > 0
    puts = s3.puts
    second = landing.from_export(str(SAMPLE))
    assert s3.puts == puts and second["objects_new"] == 0 and second["images_new"] == 0
    obj = next(k for k in s3.objects if k.startswith("raw/"))
    item = json.loads(s3.objects[obj])
    assert item["schema_version"] == 2 and item["source"]["system"] == "scraper"


def test_sync_reads_the_database_and_media_from_the_scraper_bucket(s3, monkeypatch):
    post = json.loads((SAMPLE / "posts.jsonl").read_text().splitlines()[1])  # a web post with images
    s3.media = {m["object_key"]: b"IMG" for m in post["media"]}

    @contextlib.contextmanager
    def session():
        yield type("Db", (), {"scalars": lambda self, q: [post]})()

    monkeypatch.setattr(landing, "session_scope", session)
    monkeypatch.setattr(landing, "post_row", lambda p: p)
    stats = landing.sync()
    assert stats["objects_new"] >= 1 and stats["images_new"] == len(
        {m["sha256"] for m in post["media"] if m["object_key"]}
    )
    assert all(s3.objects[k] == b"IMG" for k in s3.objects if k.startswith("images/"))
    assert landing.sync()["objects_new"] == 0  # drugi raz nic nowego


def test_a_failing_hand_over_never_fails_the_scrape_job(monkeypatch, s3):
    def boom():
        raise RuntimeError("minio down")

    monkeypatch.setattr(jobs.landing, "sync", boom)
    jobs._hand_over()  # nie rzuca


def test_hand_over_can_be_switched_off(monkeypatch, s3):
    monkeypatch.setenv("LANDING_SYNC", "false")
    settings.cache_clear()
    called = []
    monkeypatch.setattr(jobs.landing, "sync", lambda: called.append(1))
    jobs._hand_over()
    assert called == []
