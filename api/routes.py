import json
import operator
from fastapi import APIRouter, Request, BackgroundTasks
from models.connector import page_count, recreate_connector, schema_count, zip_url
from services.helpers.logger import getLogger
from services.helpers.s3 import read_object
from services.scrapers.domain_processor import PRODUCTION_CONNECTORS_FILE, add_connector_in_json_files, combine_domain, embed_domain, generate_connector_files, scrape_pages
from datetime import datetime

router = APIRouter()
logger = getLogger()


def process_domain_in_order(connector):
    # This function will be run in the background after sending the response.
    scrape_pages(connector)
    combine_domain(connector)
    embed_domain(connector)
    generate_connector_files(connector)


@router.post('/create_connector')
async def create_connector(background_tasks: BackgroundTasks, request: Request):
    data = await request.json()
    production_file_content = read_object(PRODUCTION_CONNECTORS_FILE)
    production_connectors = json.loads(production_file_content)

    if any((connector['name'].lower() == data['name'].lower() or connector['base_url'].lower() == data['base_url'].lower()) for connector in production_connectors):
        return {"success": f"Connector with name: {data['name']} already exists!"}

    connector = {
        'name': data['name'],
        'base_url': data['base_url'],
        'start_url': data['start_url'],
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    add_connector_in_json_files(connector)
    background_tasks.add_task(process_domain_in_order, connector)
    logger.info(f"Scraping started for the page: {connector['start_url']}")

    return {"success": f"Scraping started for: {connector['name']}"}


@router.get('/connectors')
async def get_connectors():
    try:
        file_content = read_object('production_connectors.json')
        connectors = json.loads(file_content)
        modified_connectors = []

        sorted_connectors = sorted(
            connectors,
            key=lambda connector: datetime.strptime(
                connector['created_at'], "%Y-%m-%d %H:%M:%S"),
            reverse=True)

        for connector in sorted_connectors:
            connector_zip_url = zip_url(connector['name'])
            scraped_pages_count = page_count(connector['base_url'])
            modified_connector = {
                'name': connector['name'],
                'export_url': connector_zip_url,
                'pages_indexed': scraped_pages_count,
                'base_url': connector['base_url'],
            }
            modified_connectors.append(modified_connector)

        return {'connectors': modified_connectors}
    except Exception as e:
        return {"status": "error", "message": "something went wrong!"}


@router.post('/recreate_connector')
async def connector_recreation(background_tasks: BackgroundTasks, request: Request):
    data = await request.json()

    try:
        background_tasks.add_task(recreate_connector, data)
        return {"status": "success", "message": "connector is being regenerated!"}
    except Exception as e:
        return {"status": "error", "message": "something went wrong!"}
