from services.helpers.s3 import read_object, upload_object
from urllib.parse import quote
from services.helpers.logger import getLogger
from services.generators.smart_search import smart_search_new_new, detect_get
from services.generators.connector_files_generator import slugify
import json
import io

logger = getLogger()


def extract_endpoints(connector):

    # get the bulk concise file for connector
    folder_name = f"source-{slugify(connector['name'])}"
    logger.info(f"Reading documentation of {connector['name']}")
    documentation_file_content = read_object(
        f"{folder_name}/documentation.txt")

    logger.info(f"Extracting links for {connector['name']}")
    # extract links using smart_search and update the connector
    extracted_links = list(set(smart_search_new_new(
        detect_get, documentation_file_content, connector)))
    connector['endpoint_count'] = len(extracted_links)
    connector['sphere_endpoints'] = extracted_links

    logger.info(
        f"Extracted {connector['endpoint_count']} links for {connector['name']}")

    endpoints_file_content = '\n'.join(extracted_links)
    upload_object(io.BytesIO(endpoints_file_content.encode(
        'utf-8')), f"{folder_name}/endpoints.txt", {
        'CacheControl': 'no-store'})
    logger.info(f"Uploaded endpoints of {connector['name']}")

    return connector
