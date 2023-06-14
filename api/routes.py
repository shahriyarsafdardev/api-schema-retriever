from fastapi.responses import JSONResponse
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
import os
from services.helpers.logger import getLogger
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