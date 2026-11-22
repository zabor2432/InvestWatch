import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def _client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def _bucket() -> str:
    return os.environ.get("PIPELINE_S3_BUCKET", "investwatch")


def ensure_bucket() -> None:
    try:
        _client().head_bucket(Bucket=_bucket())
    except ClientError:
        _client().create_bucket(Bucket=_bucket())


def get(key: str) -> bytes:
    return _client().get_object(Bucket=_bucket(), Key=key)["Body"].read()


def list_keys(prefix: str) -> list[str]:
    pages = _client().get_paginator("list_objects_v2").paginate(Bucket=_bucket(), Prefix=prefix)
    return [o["Key"] for page in pages for o in page.get("Contents", [])]
