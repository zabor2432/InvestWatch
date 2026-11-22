"""Scraper exports -> contract v2 landing objects (investwatch_common.landing), on the real sample in data/scraped/."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from investwatch_common import landing

import seed

ROOT = Path(__file__).resolve().parents[3]
SAMPLE = ROOT / "data" / "scraped" / "2026-11-22"
SCHEMA = json.loads((ROOT / "docs" / "intake-item.schema.json").read_text())
BRANDS = json.loads((ROOT / "scraper" / "config" / "brand_aliases.json").read_text())["brands"]


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.puts = 0

    def put_object(self, Bucket, Key, Body, **kw):  # noqa: N803
        self.objects[Key] = Body
        self.puts += 1

    def get_paginator(self, name):
        s3 = self

        class Pages:
            def paginate(self, Bucket, Prefix):  # noqa: N803
                yield {"Contents": [{"Key": k} for k in s3.objects if k.startswith(Prefix)]}

        return Pages()


def converted():
    out = []
    for post, load in landing.iter_export(SAMPLE):
        out += [(post, *c) for c in landing.convert(post, BRANDS, load)]
    return out


def test_every_sample_post_becomes_a_schema_valid_item_with_task_module():
    items = converted()
    assert len(items) >= 17
    for post, key, item, _ in items:
        jsonschema.validate(item, SCHEMA)
        assert item["module"] == landing.TASK_MODULE[post["first_task"]]
        assert key.startswith(f"raw/{post['platform']}/{post['external_id']}/") and key.endswith(
            ".json"
        )


def test_module_2_pages_carry_desktop_and_mobile_screenshots_and_the_firm_is_the_publisher():
    m2 = [(p, i) for p, _, i, _ in converted() if i["module"] == "self_promotion"]
    assert m2
    for post, item in m2:
        assert {im["variant"] for im in item["images"]} == {
            "desktop",
            "mobile",
        }  # reguła 8: para ekranów
        assert item["observation"]["advertised_firm"] == post["author_display_name"]


def test_module_1_firm_comes_from_the_brand_alias_in_the_query_longest_alias_wins():
    assert (
        landing.firm_for({"first_task": "registry_ads", "first_query": "XTB promocja kod"}, BRANDS)
        == "XTB"
    )
    brands = [{"brand": "A", "aliases": ["ing"]}, {"brand": "B", "aliases": ["ing bank śląski"]}]
    assert (
        landing.firm_for(
            {"first_task": "registry_ads", "first_query": "opinie ING Bank Śląski"}, brands
        )
        == "B"
    )
    assert (
        landing.firm_for({"first_task": "registry_ads", "first_query": "string"}, brands) == ""
    )  # nie w środku słowa
    assert landing.firm_for({"first_task": "shadow_advisory", "first_query": "xtb"}, BRANDS) == ""


def test_writing_twice_adds_nothing_and_images_are_stored_once_by_content():
    s3 = FakeS3()
    first = seed.put_scraped(s3, "b", SAMPLE.parent, BRANDS)
    assert first["objects_new"] >= 17 and first["images_new"] > 0 and first["objects_existing"] == 0
    puts = s3.puts
    second = seed.put_scraped(s3, "b", SAMPLE.parent, BRANDS)
    assert (
        s3.puts == puts and second["objects_new"] == 0 and second["images_new"] == 0
    )  # żadnych duplikatów
    assert all(k.startswith(("raw/", "images/")) for k in s3.objects)
    images = [k for k in s3.objects if k.startswith("images/")]
    assert len(images) == len(set(images))


def test_changed_content_is_a_new_object_and_the_old_version_stays():
    post, load = landing.iter_export(SAMPLE)[0]
    s3 = FakeS3()
    sink = landing.Landing(s3, "b")
    for key, item, assets in landing.convert(post, BRANDS, load):
        sink.write(key, item, assets)
    before = set(s3.objects)
    changed = copy.deepcopy(post)
    changed["versions"].append(
        {
            **changed["versions"][-1],
            "content": "Zmieniona treść wpisu",
            "captured_at": "2026-12-01T00:00:00+00:00",
        }
    )
    sink = landing.Landing(s3, "b")
    for key, item, assets in landing.convert(changed, BRANDS, load):
        sink.write(key, item, assets)
    new = set(s3.objects) - before
    assert len(new) == 1 and next(iter(new)).startswith("raw/")  # nowa wersja, obrazy bez zmian
    assert before <= set(s3.objects)  # stara wersja zostaje (historia)


def test_posts_without_content_or_with_unknown_task_are_skipped_and_missing_files_do_not_break_conversion():
    assert (
        landing.convert(
            {
                "first_task": "registry_sync",
                "platform": "web",
                "external_id": "x",
                "url": "https://a.pl",
                "scraped_at": "2026-11-22T00:00:00+00:00",
            },
            [],
            lambda m: b"",
        )
        == []
    )
    empty = {
        "first_task": "shadow_advisory",
        "platform": "web",
        "external_id": "x",
        "url": "https://a.pl",
        "scraped_at": "2026-11-22T00:00:00+00:00",
        "media": [],
    }
    assert (
        landing.convert(empty, [], lambda m: b"") == []
    )  # ani tekstu, ani obrazu (kontrakt tego nie przyjmie)


@pytest.mark.parametrize(
    "variant_url,expected",
    [
        ("screenshot:mobile:abc", "mobile"),
        ("screenshot:desktop:abc", "desktop"),
        ("https://x/og.jpg", "original"),
    ],
)
def test_image_variant_comes_from_the_screenshot_source_url(variant_url, expected):
    post = {
        "first_task": "shadow_advisory",
        "platform": "web",
        "external_id": "x",
        "url": "https://a.pl",
        "title": "t",
        "content": "c",
        "scraped_at": "2026-11-22T00:00:00+00:00",
        "media": [
            {
                "object_key": "web/x/a.png",
                "sha256": "a" * 64,
                "content_type": "image/png",
                "source_url": variant_url,
            }
        ],
    }
    ((_, item, assets),) = landing.convert(post, [], lambda m: b"PNG")
    assert (
        item["images"][0]["variant"] == expected
        and item["images"][0]["key"] == f"images/{'a' * 64}.png"
    )
    assert assets[0].load() == b"PNG"
