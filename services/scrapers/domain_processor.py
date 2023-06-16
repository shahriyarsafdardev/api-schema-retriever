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


def read_all_connector(filename):
    file_content = read_object(filename)
    connectors = json.loads(file_content)
    return connectors


def upload_all_connector(filename, connectors):
    upload_object(io.BytesIO(json.dumps(connectors, indent=4).encode(
        'utf-8')), filename, {'CacheControl': 'no-store'})


def add_connector_in_json_files(connector):
    airbyte_connectors = read_all_connector(AIRBYTE_CONNECTORS_FILE)
    production_connectors = read_all_connector(PRODUCTION_CONNECTORS_FILE)
    production_connector_keys = ['name', 'base_url', 'start_url', 'created_at']
    production_connector = {key: connector[key]
                            for key in production_connector_keys}
    production_connectors.append(production_connector)
    airbyte_connectors.append(connector)
    upload_all_connector(AIRBYTE_CONNECTORS_FILE, airbyte_connectors)
    upload_all_connector(PRODUCTION_CONNECTORS_FILE, production_connectors)


def update_connector_in_json_files(connector):
    airbyte_connectors = read_all_connector(AIRBYTE_CONNECTORS_FILE)
    updated_airbyte_connectors = [
        connector if connector['base_url'] == airbyte_connector['base_url'] else airbyte_connector for airbyte_connector in airbyte_connectors]
    upload_all_connector(AIRBYTE_CONNECTORS_FILE, updated_airbyte_connectors)


def scrape_pages(connector):
    logger.info("Running scrape_domain...")
    scraped_pages_count = len(scrape_domain(
        connector['start_url'], connector['base_url']))
    connector.update({'scraped_page_count': scraped_pages_count})
    update_connector_in_json_files(connector)
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished scrape_domain")


def combine_domain(connector):
    logger.info("Running combine...")
    time.sleep(5)  # Simulate time-consuming process
    updated_connector = combine(connector)
    update_connector_in_json_files(updated_connector)
    logger.info("Finished combine")


def embed_domain(connector):
    logger.info("Running embedding...")
    embedding(connector)
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished embedding")


def generate_connector_files(connector):
    create_connector_files(connector)
    logger.info("Running generate_connector_files...")
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished generate_connector_files")
