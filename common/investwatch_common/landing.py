"""Scraper post -> InvestWatch contract v2 (docs/data-contract.md), written to the pipeline bucket without duplicates.

Pure standard library (no database, no boto3 import), so the scraper and the demo seed share it.
A post is the dict shape of `app.dataset` exports (post fields + `hits`, `versions`, `media`).

Landing objects are immutable and content-addressed:
  raw/{platform}/{external_id}/{hash12}.json   one per version of a post's content
  images/{sha256}{ext}                         one per distinct image
`hash12` = sha256 of [title, text, image sha256s] (first 12 hex). Same content, same key: a second run writes nothing new,
changed content gets a new object (a new version of the document, history is kept by the pipeline's ledger).
"""

import hashlib
import json
import mimetypes
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

TASK_MODULE = {
    "registry_ads": "third_party_ads",
    "firm_marketing": "self_promotion",
    "shadow_advisory": "non_investment_companies",
}
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@dataclass(frozen=True)
class Asset:
    """An image that must exist in the pipeline bucket under `key`; `load` fetches the bytes only when it is missing."""

    key: str
    load: Callable[[], bytes]
    content_type: str


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold().strip()


def version_hash(title: str | None, text: str | None, shas: list[str]) -> str:
    return hashlib.sha256(json.dumps([title, text, shas], ensure_ascii=False).encode()).hexdigest()[
        :12
    ]


def object_key(
    platform: str, external_id: str, title: str | None, text: str | None, shas: list[str]
) -> str:
    return f"raw/{platform}/{external_id.replace('/', '_')}/{version_hash(title, text, shas)}.json"


def firm_for(post: dict, brands: list[dict]) -> str:
    """The firm an item is about. Module 2: the publisher itself. Module 1: the brand whose alias occurs in the search query
    (longest alias wins). Module 3 and unknown: ''. `brands` = `brands` of scraper/config/brand_aliases.json."""
    task, query = post.get("first_task"), _fold(post.get("first_query") or "")
    if task == "firm_marketing":
        return post.get("author_display_name") or post.get("author_handle") or ""
    if task != "registry_ads":
        return ""
    best, best_len = "", 0
    for b in brands:
        for alias in [*b["aliases"], *b.get("manual_aliases", [])]:
            a = _fold(alias)
            if len(a) > best_len and re.search(rf"(?<!\w){re.escape(a)}(?!\w)", query):
                best, best_len = b["brand"], len(a)
    return best


def _image(m: dict, load: Callable[[dict], bytes]) -> tuple[dict, Asset] | None:
    """Media row -> (contract image, asset). Screenshots carry their viewport in `source_url` ("screenshot:mobile:<id>")."""
    if not m.get("object_key") or not m.get("sha256"):
        return None
    suffix = (
        mimetypes.guess_extension(m.get("content_type") or "")
        or "." + m["object_key"].rsplit(".", 1)[-1]
    )
    if suffix.lower() not in EXTENSIONS:
        return None
    parts = (m.get("source_url") or "").split(":")
    variant = (
        parts[1]
        if parts[0] == "screenshot" and len(parts) > 2 and parts[1] in ("desktop", "mobile")
        else "original"
    )
    key = f"images/{m['sha256']}{suffix.lower()}"
    ctype = m.get("content_type") or mimetypes.guess_type(key)[0] or "image/png"
    return {"key": key, "sha256": m["sha256"], "variant": variant, "focus": "page"}, Asset(
        key, lambda: load(m), ctype
    )


def convert(
    post: dict, brands: list[dict], load: Callable[[dict], bytes]
) -> list[tuple[str, dict, list[Asset]]]:
    """-> [(landing object key, contract item, images to ensure)] one per content version, oldest first.
    The scraper keeps no per-version media, so every version carries the post's images: an old version keeps its key
    when a newer one appears (nothing is duplicated, the new version is the only new object)."""
    module = TASK_MODULE.get(post.get("first_task"))
    if module is None:
        return []
    versions = sorted(
        post.get("versions")
        or [
            {
                "title": post.get("title"),
                "content": post.get("content"),
                "transcript": post.get("transcript"),
                "captured_at": post["scraped_at"],
            }
        ],
        key=lambda v: v["captured_at"],
    )
    pairs = [p for m in post.get("media", []) if (p := _image(m, load))]
    host = (urlparse(post["url"]).hostname or "").removeprefix("www.")
    meta = {
        "scraper": {
            k: post.get(k)
            for k in ("first_task", "first_query", "first_job_id", "engagement", "outbound_links")
        }
    }
    out = []
    for v in versions:
        images, assets = [p[0] for p in pairs], [p[1] for p in pairs]
        text = "\n\n".join(x for x in (v.get("content"), v.get("transcript")) if x) or None
        if not (text or images):
            continue
        item = {
            "schema_version": 2,
            "source": {
                "system": "scraper",
                "platform": post["platform"],
                "external_id": post["external_id"],
                "url": post["url"],
            },
            "module": module,
            "observation": {
                "advertiser": {
                    "handle": post.get("author_handle") or host,
                    "name": post.get("author_display_name"),
                    "url": post.get("author_url"),
                },
                "advertised_firm": firm_for(post, brands),
            },
            "published_at": post.get("published_at"),
            "captured_at": v["captured_at"],
            "title": v.get("title"),
            "text": text,
            "lang": post.get("lang"),
            "images": images,
            "meta": meta,
        }
        key = object_key(
            post["platform"],
            post["external_id"],
            item["title"],
            text,
            [im["sha256"] for im in images],
        )
        out.append((key, item, assets))
    return out


class Landing:
    """Writer for the pipeline bucket (`s3` = boto3 client). Knows what is already there, so nothing is written twice."""

    def __init__(self, s3, bucket: str):
        self.s3, self.bucket = s3, bucket
        self.known = self._list("raw/") | self._list("images/")
        self.stats = {
            "objects_new": 0,
            "objects_existing": 0,
            "images_new": 0,
            "images_existing": 0,
        }

    def _list(self, prefix: str) -> set[str]:
        keys: set[str] = set()
        for page in self.s3.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix
        ):
            keys |= {o["Key"] for o in page.get("Contents", [])}
        return keys

    def write(self, key: str, item: dict, assets: list[Asset]) -> bool:
        """Images first (a landing object must never point at a missing image), then the object. True when the object was new."""
        for a in assets:
            if a.key in self.known:
                self.stats["images_existing"] += 1
                continue
            self.s3.put_object(
                Bucket=self.bucket, Key=a.key, Body=a.load(), ContentType=a.content_type
            )
            self.known.add(a.key)
            self.stats["images_new"] += 1
        if key in self.known:
            self.stats["objects_existing"] += 1
            return False
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(item, ensure_ascii=False).encode(),
            ContentType="application/json",
        )
        self.known.add(key)
        self.stats["objects_new"] += 1
        return True


def iter_export(directory: Path | str) -> list[tuple[dict, Callable[[dict], bytes]]]:
    """Posts of a scraper export directory (`posts.jsonl` + `media/<object key>`), each with its media loader."""
    root = Path(directory)
    posts = [
        json.loads(line)
        for line in (root / "posts.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]

    def load(m: dict) -> bytes:
        return (root / "media" / m["object_key"]).read_bytes()

    return [(p, load) for p in posts]
