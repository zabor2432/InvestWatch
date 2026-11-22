"""Odczyt obrazów z object storage (S3 API). Klucz zawsze pochodzi z bazy, nigdy od klienta."""

import os

import boto3
from botocore.config import Config


def get(key: str) -> bytes:
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["MINIO_ROOT_USER"],
        aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
    return s3.get_object(Bucket=os.environ.get("PIPELINE_S3_BUCKET", "investwatch"), Key=key)[
        "Body"
    ].read()
