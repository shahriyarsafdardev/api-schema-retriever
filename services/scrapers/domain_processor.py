import time
from services.generators.connector_files_generator import create_connector_files
from services.generators.manifest import generate_manifest
from services.helpers.json_loader import load_connectors, save_connectors
from services.helpers.logger import getLogger
from services.scrapers.scraper import scrape_domain
from services.scrapers.combine import combine
from services.scrapers.embedding import embed
from services.scrapers.link_extraction import extract_endpoints


logger = getLogger()
AIRBYTE_CONNECTORS_FILE = 'airbyte_connectors.json'
PRODUCTION_CONNECTORS_FILE = 'production_connectors.json'


def add_connector_in_json_files(connector):
    airbyte_connectors = load_connectors(AIRBYTE_CONNECTORS_FILE)
    production_connectors = load_connectors(PRODUCTION_CONNECTORS_FILE)
    production_connector_keys = ['name', 'base_url', 'start_url', 'created_at']
    production_connector = {key: connector[key]
                            for key in production_connector_keys}
    production_connectors.append(production_connector)
    airbyte_connectors.append(connector)
    save_connectors(AIRBYTE_CONNECTORS_FILE, airbyte_connectors)
    save_connectors(PRODUCTION_CONNECTORS_FILE, production_connectors)


def save_connector_in_json_files(connector):
    airbyte_connectors = load_connectors(AIRBYTE_CONNECTORS_FILE)
    updated_airbyte_connectors = [
        connector if connector['base_url'] == airbyte_connector['base_url'] else airbyte_connector for airbyte_connector in airbyte_connectors]
    save_connectors(AIRBYTE_CONNECTORS_FILE, updated_airbyte_connectors)


def scrape_pages(connector):
    logger.info("Running scrape_domain...")
    scraped_pages_count = len(scrape_domain(
        connector['start_url'], connector['base_url']))
    connector.update({'scraped_page_count': scraped_pages_count})
    save_connector_in_json_files(connector)
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished scrape_domain")


def combine_domain(connector):
    logger.info("Running combine...")
    time.sleep(5)  # Simulate time-consuming process
    updated_connector = combine(connector)
    save_connector_in_json_files(updated_connector)
    logger.info("Finished combine")


def extract_links(connector):
    logger.info("Running endpoints extraction...")
    time.sleep(5)  # Simulate time-consuming process
    updated_connector = extract_endpoints(connector)
    save_connector_in_json_files(updated_connector)
    logger.info("Finished endpoints extraction")


def embed_domain(connector):
    logger.info("Running embedding...")
    embed(connector)
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished embedding")


def generate_manifest_file(connector):
    generate_manifest(connector)
    logger.info("Running generate_manifest...")
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished generate_manifest")


def generate_connector_files(connector):
    create_connector_files(connector)
    logger.info("Running generate_connector_files...")
    time.sleep(5)  # Simulate time-consuming process
    logger.info("Finished generate_connector_files")
