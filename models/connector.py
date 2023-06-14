import io
import json
from urllib.parse import quote
from services.generators.connector_files_generator import slugify
from services.helpers.s3 import bucket_name, count_connector_schema_files, get_connector_zip_file, list_objects, read_object, upload_object


def zip_url(name):
    file_name = f"source-{slugify(name)}.zip"
    zip_url = get_connector_zip_file(file_name)
    return zip_url


def schema_count(name):
    slugified_name = slugify(name)
    schema_count = count_connector_schema_files(slugified_name)
    return schema_count


def page_count(base_url):
    quoted_base_url = quote(base_url, safe="")
    page_count = len(list_objects([quoted_base_url, ".html"]))
    return page_count


def bulk_file_url(base_url):
    quoted_base_url = quote(base_url, safe="")
    bulk_filename = quoted_base_url + '-bulk-concise' + '.md'
    return f"https://{bucket_name}.s3.amazonaws.com/{bulk_filename}"


def add_connector(connector):
    connectors = []
    filename = 'production_connectors.json'
    file_content = read_object(filename)
    connectors = json.loads(file_content)
    connectors.append(connector)
    connectors = json.dumps(connectors, indent=4)
    file_obj = io.BytesIO(connectors.encode('utf-8'))
    upload_object(file_obj, filename, extraArgs={'CacheControl': 'no-store'})
