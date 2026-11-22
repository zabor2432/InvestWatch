import json
from pathlib import Path

import jsonschema
import pytest

import seed

DEMO = Path(__file__).resolve().parents[2]  # ./demo
SCHEMA = json.loads((DEMO.parent / "docs" / "intake-item.schema.json").read_text())


def test_sample_records_are_valid_and_their_images_exist():
    records = seed.load_records(DEMO)
    ids = [(r["platform"], r["external_id"]) for r in records]
    assert len(ids) == len(set(ids))
    assert all(r["module"] in seed.MODULES for r in records)
    assert all(r["text"] or r["images"] for r in records)  # a record needs text or an image
    assert all((r["_dir"] / i["file"]).is_file() for r in records for i in r["images"])
    assert {r["module"] for r in records} == seed.MODULES  # every module has examples


def test_every_record_becomes_a_schema_valid_contract_item():
    for rec in seed.load_records(DEMO):
        _, item, _ = seed.to_item(rec)
        jsonschema.validate(item, SCHEMA)


def test_demo_has_an_observed_pair_with_history_and_a_responsive_pair():
    items = [seed.to_item(r)[1] for r in seed.load_records(DEMO)]
    pairs = {}
    for it in items:
        o = it["observation"]
        pairs.setdefault((o["advertiser"]["handle"], o["advertised_firm"]), []).append(
            it["published_at"]
        )
    assert any(
        len(set(dates)) >= 3 for dates in pairs.values()
    )  # kolejne materiały jednej pary w czasie
    variants = [{i["variant"] for i in it["images"]} for it in items]
    assert {"desktop", "mobile"} in variants  # rekord z dwoma ekranami (reguła 8)
    assert any(it["manipulated"] for it in items)


def test_real_ads_folder_adds_original_and_blurred_variant_with_labels(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "records.json").write_text("[]")
    (tmp_path / "real").mkdir()
    for name in ("xtb_original.png", "xtb_blur.png", "notes.txt"):
        (tmp_path / "real" / name).write_bytes(b"x")
    found = {
        r["external_id"]: (r["label"], bool(r["manipulated"])) for r in seed.load_records(tmp_path)
    }
    assert found == {"real-xtb_original": (False, False), "real-xtb_blur": (True, True)}


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body):  # noqa: N803
        self.objects[(Bucket, Key)] = Body


@pytest.mark.parametrize("bucket", ["investwatch"])
def test_put_all_writes_landing_objects_and_content_addressed_images_idempotently(bucket):
    s3, records = FakeS3(), seed.load_records(DEMO)
    seed.put_all(s3, bucket, records)
    first = dict(s3.objects)
    seed.put_all(s3, bucket, records)
    assert s3.objects == first  # ponowny seed nie tworzy nowych obiektów (te same klucze i treść)
    key = next(k for _, k in first if "/nordic-capital-503/" in k)
    item = json.loads(first[(bucket, key)])
    assert key.startswith("raw/instagram/nordic-capital-503/") and {
        i["variant"] for i in item["images"]
    } == {"desktop", "mobile"}
    assert all(
        (bucket, i["key"]) in first and i["key"].startswith("images/") for i in item["images"]
    )
