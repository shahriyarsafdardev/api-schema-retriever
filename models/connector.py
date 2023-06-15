import io
import json
from logging import getLogger
from urllib.parse import quote
from services.generators.connector_files_generator import create_connector_files, slugify
from services.helpers.pinecone_db import delete_vectors
from services.helpers.s3 import bucket_name, count_connector_schema_files, delete_connector_zip_file, delete_folder, get_connector_zip_file, list_objects, read_object, upload_object
from services.scrapers.embedding import embedding


logger = getLogger()


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


def remove_connector_data(connector_name, base_documentation_url):
    logger.info(f"Removing data for connector : {base_documentation_url}")
    s3_folder_name = f"source-{slugify(connector_name)}"
    file_name = f"source-{slugify(connector_name)}.zip"
    # Delete existing s3 files for the domain
    delete_folder(s3_folder_name)
    # Delete existing vectors for the domain
    delete_vectors({'domain_base_url': base_documentation_url})
    # Delete existing zip url for the domain
    delete_connector_zip_file(file_name)
    logger.info(f"Removed data for connector : {base_documentation_url} \n")


def recreate_connector(connector):
    remove_connector_data(
        connector['name'], connector['base_url'])
    logger.info(
        f"\nStart generating embeddings for connector : {connector['base_url']}")
    embedding(connector)
    logger.info(
        f"\nGenerated embeddings for connector : {connector['base_url']}")
    create_connector_files(connector)
