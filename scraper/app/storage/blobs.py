"""Object storage for images and video thumbnails (MinIO via the S3 API)."""

import hashlib
import json
import mimetypes
import time
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.http import HttpClient
from app.log import log
from app.settings import settings


@lru_cache
def _s3():
    s = settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket(attempts: int = 30) -> None:
    """Create the media bucket if missing; waits for MinIO to come up."""
    s3, bucket = _s3(), settings().s3_bucket
    for attempt in range(1, attempts + 1):
        try:
            try:
                s3.head_bucket(Bucket=bucket)
            except ClientError:
                s3.create_bucket(Bucket=bucket)
                log.info("bucket_created", bucket=bucket)
            # media is shown by the dashboard straight from object storage: anonymous read-only access
            s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Principal": {"AWS": ["*"]}, "Action": ["s3:GetObject"],
                               "Resource": [f"arn:aws:s3:::{bucket}/*"]}],
            }))
            return
        except (BotoCoreError, ClientError) as exc:
            if attempt == attempts:
                raise
            log.info("waiting_for_object_storage", attempt=attempt, error=str(exc)[:200])
            time.sleep(2)


class StoredBlob:
    def __init__(self, bucket: str, key: str, content_type: str, size: int, sha256: str):
        self.bucket, self.key, self.content_type, self.size, self.sha256 = bucket, key, content_type, size, sha256


def download_to_bucket(http: HttpClient, url: str, key_prefix: str) -> StoredBlob | None:
    """Download `url` and store it under `<key_prefix>/<sha256[:16]><ext>`. None on failure or oversize."""
    s = settings()
    try:
        resp = http.get(url)
    except Exception as exc:
        log.warning("media_download_failed", url=url, error=str(exc))
        return None
    if resp.status_code != 200:
        log.warning("media_download_failed", url=url, status=resp.status_code)
        return None
    data = resp.content
    if len(data) > s.media_max_bytes:
        log.warning("media_too_large", url=url, size=len(data))
        return None
    ctype = resp.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
    if not ctype.startswith("image/"):
        log.warning("media_not_image", url=url, content_type=ctype)
        return None
    digest = hashlib.sha256(data).hexdigest()
    ext = mimetypes.guess_extension(ctype) or ""
    key = f"{key_prefix}/{digest[:16]}{ext}"
    _s3().put_object(Bucket=s.s3_bucket, Key=key, Body=data, ContentType=ctype)
    return StoredBlob(s.s3_bucket, key, ctype, len(data), digest)


def upload_bytes(data: bytes, content_type: str, key_prefix: str) -> StoredBlob | None:
    """Store bytes captured by a collector (e.g. a screenshot) under `<key_prefix>/<sha256[:16]><ext>`."""
    s = settings()
    if len(data) > s.media_max_bytes:
        log.warning("media_too_large", key_prefix=key_prefix, size=len(data))
        return None
    digest = hashlib.sha256(data).hexdigest()
    key = f"{key_prefix}/{digest[:16]}{mimetypes.guess_extension(content_type) or ''}"
    try:
        _s3().put_object(Bucket=s.s3_bucket, Key=key, Body=data, ContentType=content_type)
    except (BotoCoreError, ClientError) as exc:
        log.warning("media_upload_failed", key=key, error=str(exc)[:200])
        return None
    return StoredBlob(s.s3_bucket, key, content_type, len(data), digest)
