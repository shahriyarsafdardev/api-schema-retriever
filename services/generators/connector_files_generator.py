import io
import re
import json
import inflect
import zipfile
from collections import defaultdict
from urllib.parse import quote, urlparse
from analysis.compare_authentication import get_langchain_response
from services.helpers.logger import getLogger
from services.helpers.s3 import read_object, upload_object, bucket_name
from services.generators.schemas import generate_schemas

logger = getLogger()
p = inflect.engine()

prompt_examples = """
Url: endpoint
Description: This endpoint returns ..........
Type: corresponding restful api method
Returned Object: a single word representing the object being returned by this endpoint
"""


def slugify(s):
    s = s.lower()
    s = re.sub(r'[^a-z0-9 -]', '', s)
    s = re.sub(r'\s+', '-', s)
    s = s.strip()
    return s


def string_to_dict(s):
    try:
        lines = s.split('\n')
        d = {}
        for line in lines:
            if line:  # Ignore empty lines
                key, value = line.split(': ')
                d[key.strip()] = value.strip()
        return d
    except Exception as e:
        return None


def generate_schemas_with_state(base_documentation_url, endpoint):
    endpoint_details = string_to_dict(get_langchain_response(base_documentation_url,
                                                             f"""Describe the {endpoint} endpoint in a format that matches the following examples: {prompt_examples}.
        Note that the "Returned Object" should always be plural, lowercase with underscores instead of spaces."""))

    if endpoint_details is not None and \
        "Returned Object" in endpoint_details and \
        "/" not in endpoint_details["Returned Object"] and \
        "None" not in endpoint_details["Returned Object"] and \
            " " not in endpoint_details["Returned Object"]:

        return endpoint_details

    return None


def generate_file_name(url):
    try:
        parsed_url = urlparse(url)
        no_scheme_url = parsed_url.netloc + parsed_url.path
        filename = re.sub(r'[^a-zA-Z0-9_-]+', '-',
                          no_scheme_url).replace('.', '-')
        filename = re.sub(r'^[-_]+|[-_]+$', '', filename)

        return filename
    except Exception as e:
        logger.error(
            f"Something went wrong while generating file name: {url} - {e}")
        return "Error"


def create_connector_files(connector, schema_objects=None):
    logger.info(f"Read short urls from S3 for {connector['name']}")
    logger.info(f"Short urls to generate schema: {connector['name']}")

    folder_name = f"source-{slugify(connector['name'])}"

    schema_objects = generate_schemas(
        connector['name'], connector['base_url'], folder_name)

    logger.info('All endpoints have been processed')

    if schema_objects:
        # step 3 - upload bulk concise and schema files
        logger.info('Uploading schemas to S3')
        zip_file_key = f"{folder_name}.zip"
        zip_buffer = io.BytesIO()

        # read and upload concise bulk file
        quoted_base_url = quote(connector['base_url'], safe="")
        bulk_concise_file = read_object(f"{quoted_base_url}-bulk-concise.md")
        upload_object(io.BytesIO(bulk_concise_file.encode('utf-8')),
                      f"{folder_name}/{quoted_base_url}-bulk-concise.md")
        with zipfile.ZipFile(zip_buffer, mode='a', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(
                f"{folder_name}/{quoted_base_url}-bulk-concise.md", bulk_concise_file)

        for object_name, schema in schema_objects.items():
            formatted_schema = json.dumps(schema, indent=4)
            upload_object(io.BytesIO(formatted_schema.encode(
                'utf-8')), f"{folder_name}/schemas/{object_name}.json", {'CacheControl': 'no-store'})
            with zipfile.ZipFile(zip_buffer, mode='a', compression=zipfile.ZIP_STORED) as archive:
                archive.writestr(
                    f"{folder_name}/schemas/{object_name}.json", formatted_schema)

        zip_buffer.seek(0)
        upload_object(zip_buffer, zip_file_key, {'CacheControl': 'no-store'})
        logger.info('source zip folder link :')
        logger.info(f"https://{bucket_name}.s3.amazonaws.com/{zip_file_key}")
        logger.info(f"Created schema for connector : {connector['base_url']}")
