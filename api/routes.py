import json
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
import os
from services.helpers.logger import getLogger
from services.helpers.s3 import count_connector_schema_files, get_connector_zip_file, read_object
from services.scrapers.scraper import scrape_domain
import asyncio

router = APIRouter()
logger = getLogger()

@router.post('/scrape_domain')
async def scrape_domain_api(background_tasks: BackgroundTasks,request: Request):
    data = await request.json()

    background_tasks.add_task(scrape_domain, data['page_url'], data['base_domain_url'], 4, True)

    logger.info(f"Scraping started for the page: {data['page_url']}")

    return {"success": f"Scraping started for: {data['page_url']}"}


@router.get('/connectors')
async def get_connectors():
    file_content = read_object('airbyte_lowcode_connectors.json')
    connectors = json.loads(file_content)
    modified_connectors = []
    for connector in connectors:
        connector_zip_url = get_connector_zip_file(connector['name'])
        schema_files_count = count_connector_schema_files(connector['name'])
        modified_connector = {
            'name': connector['name'],
            'export_url': connector_zip_url,
            'pages_indexed': connector['scraped_page_count'],
            'schemas_indexed': schema_files_count
        }
        modified_connectors.append(modified_connector)

    return { 'connectors': modified_connectors }
