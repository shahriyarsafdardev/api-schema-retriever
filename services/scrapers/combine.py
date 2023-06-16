from collections import OrderedDict
import io
import json
from urllib.parse import quote
import html2text
from logging import getLogger
from services.generators.connector_files_generator import slugify
from services.generators.smart_search import detect_get, smart_search_new_new
from services.helpers.s3 import list_objects, read_object, upload_object


logger = getLogger()
AIRBYTE_CONNECTORS_FILE = 'airbyte_connectors.json'


def convert_html_to_md(text):
    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    converter.body_width = 0
    return converter.handle(text)


def combine(connector):
    page_count = connector.get('scraped_page_count', None)
    if not page_count:
        logger.info("No pages scrapped for {}".format(connector['name']))
        return

    logger.info("Creating md files for {}".format(connector['name']))
    base_url = connector['base_url']
    quoted_base_url = quote(base_url, safe="")
    file_keys = list_objects([quoted_base_url, ".html"])

    combined_file_content = ''
    for file_key in file_keys:
        logger.info("Generating .md file for {}".format(file_key))
        file_content = convert_html_to_md(read_object(file_key))
        upload_object(io.BytesIO(file_content.encode('utf-8')),
                      file_key.rsplit('.html', 1)[0] + ".md", {
            'CacheControl': 'no-store'})
        combined_file_content += file_content + "\n\n"

    upload_object(io.BytesIO(combined_file_content.encode(
        'utf-8')), quoted_base_url + '-bulk' + '.md', {
        'CacheControl': 'no-store'})

    # this code splits the text to paragraphs then converts to ordereddict to ensure uniqueness and keep the correct order
    paragraphs = combined_file_content.split("\n\n")
    ordered_dict = OrderedDict.fromkeys(paragraphs)
    unique_paragraphs = list(ordered_dict.keys())
    upload_object(io.BytesIO("\n\n".join(unique_paragraphs).encode(
        'utf-8')), quoted_base_url + '-bulk-concise' + '.md', {
        'CacheControl': 'no-store'})

    # this will add a new documentation.txt file in connector's directory
    folder_name = f"source-{slugify(connector['name'])}"
    upload_object(io.BytesIO("\n\n".join(unique_paragraphs).encode(
        'utf-8')), f"{folder_name}/documentation.txt", {
        'CacheControl': 'no-store'})
    logger.info("Uploaded documentation file for {}".format(connector['name']))

    return connector
