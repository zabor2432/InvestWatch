"""Puts demo and collected records into the pipeline bucket (MinIO) as contract-v2 landing objects.
Stand-in for the scraper: the pipeline only sees `raw/{platform}/{external_id}/{hash12}.json` (docs/data-contract.md).

Sources (the ./demo directory, mounted at /demo):
  data/records.json       fictional sample records (images in images/) (incl. one observed advertiser with 3 posts over time)
  collected/records.json  records (images in collected/images/) gathered from public pages by demo/collect (git-ignored, optional)
  /data/scraped/<date>/   scraper exports (posts.jsonl + media), converted by investwatch_common.landing
  real/                   real ads for research (git-ignored); an image whose name contains "zamazane" or "blur"
                          is the variant with the risk information made unreadable (label: violation)

A source record is the contract without storage details: images are file names ({file, variant, focus}) next to the json;
the seed uploads them content-addressed (`images/{sha256}.ext`) and fills `key` and `sha256`.
"""

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from investwatch_common import landing

DEMO = Path(os.environ.get("DEMO_DIR", "/demo"))
SCRAPED = Path(
    os.environ.get("SCRAPED_DIR", "/data/scraped")
)  # exports of the scraper (data/scraped/<date>/)
SCRAPER_CONFIG = Path(
    os.environ.get("SCRAPER_CONFIG_DIR", "/scraper-config")
)  # brand_aliases.json: firm of module 1 items
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
VIOLATION_MARKS = ("zamazane", "blur")
MODULES = {"third_party_ads", "self_promotion", "non_investment_companies"}
REAL_BLUR = {"rules": ["5", "6"], "recipe": "informacja o ryzyku zamazana ręcznie"}


def load_records(demo: Path = DEMO) -> list[dict]:
    """Source records with `_dir` (where their image files are). Real ads: original = no violation, blurred = violation."""
    records = []
    for records_file, images_dir in (
        (demo / "data" / "records.json", demo / "images"),
        (demo / "collected" / "records.json", demo / "collected" / "images"),
    ):
        if records_file.is_file():
            records += [
                {**r, "_dir": images_dir}
                for r in json.loads(records_file.read_text(encoding="utf-8"))
            ]
    real = demo / "real"
    for f in sorted(real.glob("*")) if real.is_dir() else []:
        if f.suffix.lower() in IMAGE_SUFFIXES:
            blurred = any(m in f.stem.lower() for m in VIOLATION_MARKS)
            records.append(
                {
                    "platform": "web",
                    "external_id": f"real-{f.stem}",
                    "module": "self_promotion",
                    "url": f"https://example.invalid/real/{f.name}",
                    "advertiser": {"handle": "xtb", "name": "XTB"},
                    "advertised_firm": "XTB",
                    "published_at": datetime.fromtimestamp(f.stat().st_mtime, UTC).isoformat(),
                    "text": None,
                    "label": blurred,
                    "images": [{"file": f.name, "variant": "original", "focus": "page"}],
                    "manipulated": REAL_BLUR if blurred else None,
                    "_dir": real,
                }
            )
    return records


def to_item(rec: dict) -> tuple[str, dict, dict[str, bytes]]:
    """Source record -> (landing object key, contract-v2 item, {image key: bytes})."""
    blobs, images = {}, []
    for im in rec["images"]:
        data = (rec["_dir"] / im["file"]).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        key = f"images/{sha}{Path(im['file']).suffix.lower()}"
        blobs[key] = data
        images.append({"key": key, "sha256": sha, "variant": im["variant"], "focus": im["focus"]})
    item = {
        "schema_version": 2,
        "source": {
            "system": "demo",
            "platform": rec["platform"],
            "external_id": rec["external_id"],
            "url": rec["url"],
        },
        "module": rec["module"],
        "observation": {
            "advertiser": rec["advertiser"],
            "advertised_firm": rec.get("advertised_firm", ""),
        },
        "published_at": rec.get("published_at"),
        "captured_at": rec.get("captured_at")
        or rec["published_at"],  # deterministic: re-seeding writes the same objects
        "title": rec.get("title"),
        "text": rec.get("text"),
        "images": images,
        "label": rec.get("label"),
        "manipulated": rec.get("manipulated"),
        "meta": rec.get("meta", {}),
    }
    key = landing.object_key(
        rec["platform"],
        rec["external_id"],
        item["title"],
        item["text"],
        [i["sha256"] for i in images],
    )
    return key, item, blobs


def client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def wait_for_storage(s3, bucket: str, tries: int = 30, delay: float = 2.0) -> None:
    """MinIO starts in parallel with the seed: wait until it answers, create the bucket if missing."""
    for i in range(tries):
        try:
            try:
                s3.head_bucket(Bucket=bucket)
            except ClientError:
                s3.create_bucket(Bucket=bucket)
            return
        except (BotoCoreError, ClientError) as e:
            if i == tries - 1:
                raise
            print(f"storage not ready ({type(e).__name__}), attempt {i + 1}/{tries}")
            time.sleep(delay)


def put_all(s3, bucket: str, records: list[dict]) -> None:
    for rec in records:
        key, item, blobs = to_item(rec)
        for image_key, data in blobs.items():
            s3.put_object(Bucket=bucket, Key=image_key, Body=data)
        s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(item, ensure_ascii=False).encode())


def put_scraped(s3, bucket: str, root: Path, brands: list[dict]) -> dict:
    """Scraper exports (`<root>/<name>/posts.jsonl` + media) -> contract v2 landing objects; what is already there is skipped."""
    sink = landing.Landing(s3, bucket)
    for export in sorted(root.glob("*/posts.jsonl")) if root.is_dir() else []:
        for post, load in landing.iter_export(export.parent):
            for key, item, assets in landing.convert(post, brands, load):
                sink.write(key, item, assets)
    return sink.stats


def main() -> None:
    bucket = os.environ.get("PIPELINE_S3_BUCKET", "investwatch")
    s3 = client()
    wait_for_storage(s3, bucket)
    records = load_records()
    put_all(s3, bucket, records)
    print(f"seeded {len(records)} records")
    aliases = SCRAPER_CONFIG / "brand_aliases.json"
    brands = json.loads(aliases.read_text(encoding="utf-8"))["brands"] if aliases.is_file() else []
    print("scraped samples:", put_scraped(s3, bucket, SCRAPED, brands))


if __name__ == "__main__":
    main()
