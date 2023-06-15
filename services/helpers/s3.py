import io
import re
import boto3
from botocore.config import Config
from services.helpers.config import settings
from services.helpers.logger import getLogger

logger = getLogger()
config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    },
    max_pool_connections=50
)

s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.sphere_aws_access_key_id,
    aws_secret_access_key=settings.sphere_aws_secret_access_key,
    config=config
)

bucket_name = settings.sphere_aws_s3_bucket_name


def slugify(s):
    s = s.lower()
    s = re.sub(r'[^a-z0-9 -]', '', s)
    s = re.sub(r'\s+', '-', s)
    s = s.strip()
    return s


def upload_object(file, key, extraArgs={}, verbose=False):
    try:
        s3_client.upload_fileobj(file, bucket_name, key, ExtraArgs=extraArgs)
        if verbose:
            logger.info(f"Uploaded file to S3 bucket {bucket_name} with key: {key}")
        return True
    except Exception as e:
        logger.error(f"Something went wrong while saving to S3: {e}")


def read_object(key, verbose=False):
    try:
        s3_object = s3_client.get_object(Bucket=bucket_name, Key=key)
        if verbose:
            logger.info(f"Read object from S3 bucket {bucket_name} with key: {key}")
        return s3_object['Body'].read().decode('utf-8')
    except Exception as e:
        logger.error(f"Something went wrong while reading from S3: {e}")


def delete_object(key, verbose=False):
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=key)
        if verbose:
            logger.info(f"Deleted file from S3 bucket {bucket_name} with key: {key}")
    except Exception as e:
        logger.error(f"An error occurred while deleting the file: {e}")

def delete_folder(folder_name,verbose=False):
    try:
        for obj in s3_client.list_objects(Bucket=bucket_name, Prefix=folder_name)['Contents']:
            s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
            if verbose:
                logger.info(f"Deleted file {obj['Key']} from S3 bucket {bucket_name}")
    except Exception as e:
        logger.error(f"An error occurred while deleting the file: {e}")


def list_objects(file_name_filters=[], verbose=False):
    keys = []
    kwargs = {'Bucket': bucket_name}
    if file_name_filters[0]:
        kwargs['Prefix'] = file_name_filters[0]
    while True:
        resp = s3_client.list_objects_v2(**kwargs)
        if 'Contents' in resp:
            for obj in resp['Contents']:
                if all(filter in obj['Key'] for filter in file_name_filters):
                    keys.append(obj['Key'])
        try:
            kwargs['ContinuationToken'] = resp['NextContinuationToken']
        except KeyError:
            break
    if verbose:
        logger.info(f"Retrieved object list from S3 bucket {bucket_name}")
    return keys


def count_connector_schema_files(connector_name):
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(
            Bucket=bucket_name, Prefix=f"source-{connector_name}/schemas/")

        file_count = 0
        for page in page_iterator:
            file_count += len([obj for obj in page.get('Contents',
                            []) if not obj['Key'].endswith('/')])

        logger.info(f"Counted {file_count} schema files for {connector_name}")
        return file_count
    except Exception as e:
        logger.error(f"An error occurred while counting the files: {e}")
        return 0


def get_connector_zip_file(file_name):
    try:
        objects = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=file_name)
        for obj in objects.get('Contents', []):
            if obj['Key'] == file_name:
                logger.info(f"Zip file {file_name} exists in S3 bucket {bucket_name}")
                return f"https://{bucket_name}.s3.amazonaws.com/{file_name}"
        logger.info(f"Zip file {file_name} does not exist in S3 bucket {bucket_name}")
        return None
    except Exception as e:
        logger.error(f"An error occurred while checking for the zip file: {e}")
        return None
