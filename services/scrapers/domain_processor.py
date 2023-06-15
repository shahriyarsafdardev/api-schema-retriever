import time
from services.generators.connector_files_generator import create_connector_files
from services.helpers.s3 import read_object, upload_object
from services.helpers.logger import getLogger
import json
import io
from services.scrapers.scraper import scrape_domain
from services.scrapers.combine import combine
from services.scrapers.embedding import embedding


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
    production_connectors.append(connector)
    connector.update({'scraped_page_count': pages_count})
    airbyte_connectors.append(connector)
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
    logger.info("Running combine...")
    time.sleep(5)  # Simulate time-consuming process
    combine(connector_name)
    logger.info("Finished combine")


def embed_domain(connector_name):
    logger.info("Running embedding...")
    embedding(connector_name)
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished embedding")


def generate_connector_files(connector_name, documentation_base_url):
    create_connector_files(connector_name, documentation_base_url)
    logger.info("Running generate_connector_files...")
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished generate_connector_files")
