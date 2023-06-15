import json
from fastapi import APIRouter, Request, BackgroundTasks
from models.connector import add_connector, page_count, schema_count, zip_url
from services.generators.connector_files_generator import recreate_connector
from services.helpers.logger import getLogger
from services.helpers.s3 import read_object
from services.scrapers.domain_processor import PRODUCTION_CONNECTORS_FILE, combine_domain, embed_domain, generate_connector_files, scrape_pages

router = APIRouter()
logger = getLogger()


def process_domain_in_order(data):
    # This function will be run in the background after sending the response.
    scrape_pages(data['name'], data['page_url'], data['base_domain_url'])
    combine_domain(data['name'])
    embed_domain(data['name'])
    generate_connector_files(data['name'], data['base_domain_url'])


@router.post('/create_connector')
async def create_connector(background_tasks: BackgroundTasks, request: Request):
    data = await request.json()
    production_file_content = read_object(PRODUCTION_CONNECTORS_FILE)
    production_connectors = json.loads(production_file_content)
    for connector in production_connectors:
        if connector['name'].lower() == data['name'].lower() or connector['base_url'].lower() == data['base_domain_url'].lower():
            return {"success": f"Connector with name: {data['name']} already exists!"}
    background_tasks.add_task(process_domain_in_order, data)
    logger.info(f"Scraping started for the page: {data['page_url']}")

    return {"success": f"Scraping started for: {data['page_url']}"}


@router.get('/connectors')
async def get_connectors():
    try:
        file_content = read_object('production_connectors.json')
        connectors = json.loads(file_content)
        modified_connectors = []

        for connector in connectors:
            connector_zip_url = zip_url(connector['name'])
            scraped_pages_count = page_count(connector['base_url'])
            schema_files_count = schema_count(connector['name'])
            modified_connector = {
                'name': connector['name'],
                'export_url': connector_zip_url,
                'pages_indexed': scraped_pages_count,
                'schemas_indexed': schema_files_count,
                'base_url': connector['base_url']
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
