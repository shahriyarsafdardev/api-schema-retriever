import time
from services.generators.connector_files_generator import create_connector_files
from services.helpers.pinecone_db import store_chunks
from services.helpers.s3 import read_object, upload_object, list_objects
from urllib.parse import quote
from services.helpers.logger import getLogger
import json
import html2text
import re
import io
from services.scrapers.scraper import scrape_domain
from collections import OrderedDict
from services.scrapers.embedding_helper import split_into_chunks, text_slice_to_vector
from services.generators.smart_search import smart_search_new_new, detect_get


logger = getLogger()
AIRBYTE_CONNECTORS_FILE = 'airbyte_connectors.json'
PRODUCTION_CONNECTORS_FILE = 'production_connectors.json'


def add_connector_in_json_files(connector_name, page_url, base_domain_url, pages_count):
    airbyte_file_content = read_object(AIRBYTE_CONNECTORS_FILE)
    airbyte_connectors = json.loads(airbyte_file_content)
    production_file_content = read_object(PRODUCTION_CONNECTORS_FILE)
    production_connectors = json.loads(production_file_content)
    connector = {
        'name': connector_name,
        'base_url': base_domain_url,
        'start_url': page_url
    }
    airbyte_connectors.append(connector.update({'scraped_page_count': pages_count}))
    production_connectors.append(connector)
    upload_object(io.BytesIO(json.dumps(airbyte_connectors, indent=4).encode(
            'utf-8')), AIRBYTE_CONNECTORS_FILE, {'CacheControl': 'no-store'})
    upload_object(io.BytesIO(json.dumps(production_connectors, indent=4).encode(
            'utf-8')), PRODUCTION_CONNECTORS_FILE, {'CacheControl': 'no-store'})


def scrape_pages(connector_name, page_url, base_domain_url):
    logger.info("Running scrape_domain...")
    scraped_pages_count = len(scrape_domain(page_url, base_domain_url))
    add_connector_in_json_files(connector_name, page_url, base_domain_url, scraped_pages_count)
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished scrape_domain")


def combine_domain(connector_name):
    logger.info("Running batch_combine...")
    time.sleep(5)  # Simulate time-consuming process
    unit_combine(connector_name)
    logger.info("Finished batch_combine")


def embed_domain(connector_name):
    logger.info("Running batch_embedding...")
    unit_embeddings(connector_name)
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished batch_embedding")


def generate_connector_files(connector_name, documentation_base_url):
    create_connector_files(connector_name, documentation_base_url)
    logger.info("Running generate_connector_files...")
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished generate_connector_files")


def convert_html_to_md(text):
    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.ignore_images = True
    converter.body_width = 0
    return converter.handle(text)

def unit_combine(connector_name):
    file_content = read_object(AIRBYTE_CONNECTORS_FILE)
    connectors = json.loads(file_content)

    for connector in connectors:
        if connector['name'] != connector_name:
            continue

        page_count = connector.get('scraped_page_count', None)
        if not page_count or connector['airbyte_status'] != 'lowcode-connector':
            logger.info("No pages scrapped for {}".format(connector['name']))
            return

        logger.info("Creating md files for {}".format(connector['name']))
        base_url = connector['base_url']
        quoted_base_url = quote(base_url, safe="")
        file_keys = list_objects([quoted_base_url, ".html"])

        combined_file_content = ''
        for file_key in file_keys[:20]:
            logger.info("Generating .md file for {}".format(file_key))
            file_content = convert_html_to_md(read_object(file_key))
            upload_object(io.BytesIO(file_content.encode('utf-8')), file_key.rsplit('.html', 1)[0] + ".md")
            combined_file_content += file_content + "\n"

        upload_object(io.BytesIO(combined_file_content.encode('utf-8')), quoted_base_url + '-bulk' + '.md')

        # this code splits the text to paragraphs then converts to ordereddict to ensure uniqueness and keep the correct order
        paragraphs = combined_file_content.split("\n\n")
        ordered_dict = OrderedDict.fromkeys(paragraphs)
        unique_paragraphs = list(ordered_dict.keys())
        upload_object(io.BytesIO("\n\n".join(unique_paragraphs).encode('utf-8')), quoted_base_url + '-bulk-concise' + '.md')

        logger.info(f"Extracting links for {connector['name']}")
        extracted_links = smart_search_new_new(detect_get, "\n\n".join(unique_paragraphs), connector)

        extracted_links = list(set(extracted_links))
        connector['endpoint_count'] = len(extracted_links)
        connector['sphere_endpoints'] = extracted_links

        updated_connectors = json.dumps(connectors, indent=4)
        file_obj = io.BytesIO(updated_connectors.encode('utf-8'))
        upload_object(file_obj, AIRBYTE_CONNECTORS_FILE, extraArgs={'CacheControl': 'no-store'})
        break


def unit_embeddings(connector_name):
    file_content = read_object(AIRBYTE_CONNECTORS_FILE)
    connectors = json.loads(file_content)

    for connector in connectors:
        if connector['name'] != connector_name:
            continue

        # reading the concise bulk file
        if connector['airbyte_status'] != 'lowcode-connector':
            return

        quoted_base_url = quote(connector['base_url'], safe="")
        concise_bulk_file = read_object(quoted_base_url + '-bulk-concise' + '.md')

        # generating chunks and storing to pinecone
        chunks = split_into_chunks(concise_bulk_file)
        logger.info('Generated {} chunks for {}'.format(len(chunks), connector["name"]))
        chunks = [text_slice_to_vector(chunk, connector['base_url']) for chunk in chunks]
        logger.info('Generated embeddings for {}'.format(connector["name"]))
        store_chunks(chunks)
        logger.info('Generated vectors for {}'.format(connector["name"]))
        break
