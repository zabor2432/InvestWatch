"""Hands scraped posts over to the InvestWatch pipeline: contract v2 objects in the pipeline bucket (docs/data-contract.md).

    python -m app.landing sync                     # every post in the scraper database
    python -m app.landing from-export <dir>        # a data/scraped/<date> export (no database needed)

Runs by itself after every job (LANDING_SYNC) and on demand (`POST /landing/sync`). The conversion and the writer are
`investwatch_common.landing`: objects and images are content-addressed, so what already is in the bucket (ours or an
earlier sync) is skipped, a changed post adds one new object and nothing is ever duplicated or overwritten.
"""

import argparse
import json
from collections.abc import Callable

from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from investwatch_common import landing as contract
from investwatch_common.db import session_scope
from investwatch_common.models import Post

from app.dataset import post_row
from app.log import configure, log
from app.settings import settings
from app.storage.blobs import _s3


def _brands() -> list[dict]:
    return json.loads((settings().config_dir / "brand_aliases.json").read_text(encoding="utf-8"))["brands"]


def _sink() -> contract.Landing:
    s3, bucket = _s3(), settings().pipeline_bucket
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)
    return contract.Landing(s3, bucket)


def _media(m: dict) -> bytes:
    return _s3().get_object(Bucket=settings().s3_bucket, Key=m["object_key"])["Body"].read()


def _land(sink: contract.Landing, posts: list[tuple[dict, Callable[[dict], bytes]]]) -> dict:
    brands = _brands()
    for post, load in posts:
        for key, item, assets in contract.convert(post, brands, load):
            sink.write(key, item, assets)
    log.info("landing_done", **sink.stats)
    return sink.stats


def sync() -> dict:
    """All posts of the scraper database -> pipeline bucket."""
    with session_scope() as db:
        rows = [
            post_row(p)
            for p in db.scalars(
                select(Post).options(selectinload(Post.hits), selectinload(Post.versions), selectinload(Post.media))
            )
        ]
    return _land(_sink(), [(row, _media) for row in rows])


def from_export(directory: str) -> dict:
    """A scraper export directory -> pipeline bucket."""
    return _land(_sink(), contract.iter_export(directory))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["sync", "from-export"])
    p.add_argument("dir", nargs="?")
    args = p.parse_args()
    configure(settings().log_level)
    result = sync() if args.action == "sync" else from_export(args.dir)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
