import os
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import config

def upload_file_to_s3(filepath: str, key: str) -> str:
    """Uploads file to configured S3 bucket. Returns the object key used.
    Raises on failure.
    """
    # Let boto3 read from env if credentials are set there
    s3 = boto3.client('s3', region_name=config.AWS_REGION or None)
    bucket = config.S3_BUCKET_NAME
    if not bucket:
        raise RuntimeError('S3_BUCKET_NAME not configured')

    try:
        s3.upload_file(filepath, bucket, key)
        return key
    except (BotoCoreError, ClientError) as e:
        raise

def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    s3 = boto3.client('s3', region_name=config.AWS_REGION or None)
    bucket = config.S3_BUCKET_NAME
    return s3.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=expires_in)
