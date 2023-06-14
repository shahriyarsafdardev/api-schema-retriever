import json
from fastapi import APIRouter, Request, BackgroundTasks
from models.connector import add_connector, page_count, schema_count, zip_url
from services.generators.connector_files_generator import create_empty_files_on_s3
from services.helpers.logger import getLogger
from services.helpers.s3 import read_object
from services.scrapers.scraper import scrape_domain

router = APIRouter()
logger = getLogger()

@router.post('/scrape_domain')
async def scrape_domain_api(background_tasks: BackgroundTasks, request: Request):
    data = await request.json()
    background_tasks.add_task(scrape_domain, data['page_url'], data['base_domain_url'], 4, True)
    logger.info(f"Scraping started for the page: {data['page_url']}")

    add_connector({
        'name': data['name'],
        'base_url': data['base_domain_url'],
        'start_url': data['page_url']
    })

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

        return { 'connectors': modified_connectors }
    except Exception as e:
        return { "status": "error", "message": "something went wrong!" }


@router.post('/recreate_connector')
async def recreate_connector(request: Request):
    data = await request.json()
    try:
        create_empty_files_on_s3(data['name'])
        return { "status": "success", "message": "connector is being regenerated!" }
    except Exception as e:
        return { "status": "error", "message": "something went wrong!" }
