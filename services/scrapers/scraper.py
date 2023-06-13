import requests
from bs4 import BeautifulSoup
import io
from services.helpers.config import settings
from services.helpers.s3 import upload_object
from urllib.parse import urljoin, urlparse, urlunparse, quote
from tqdm import tqdm
from services.helpers.logger import getLogger
from scrapingbee import ScrapingBeeClient
import concurrent.futures
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from requests.exceptions import HTTPError, InvalidSchema, ConnectTimeout

logger = getLogger()

from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium import webdriver
from bs4 import BeautifulSoup

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


def get_html_with_selenium(page_url, verbose=False):
    """
    This function uses Selenium with Firefox to get the HTML content of the given page URL.

    :param page_url: String containing the URL from which the HTML content is to be downloaded.
    :return: String containing the HTML content of the webpage. 
    """

    options = webdriver.FirefoxOptions()

    options.add_argument("--headless")
    options.binary_location = '/Applications/Firefox.app/Contents/MacOS/firefox'
    
    service = Service(GeckoDriverManager().install())
    
    # this is where it started to scrap the page
    driver = webdriver.Firefox(service=service, options=options)
    
   
    driver.set_page_load_timeout(30)

    try:        
        driver.get(page_url)
        # time.sleep(2)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        logger.info("Page HTML: %s", driver.page_source)
    
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        if verbose:
            logger.info("Page HTML: %s", soup.prettify())
        
        
    except Exception as e:
        
        logger.error("Error parsing HTML: %s", str(e), exc_info=True)
        soup = None
    
    
    driver.quit()
    
    return str(soup)

def download_html(page_url, verbose=False):
    try:
        response = requests.get(page_url, timeout=60)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Use Selenium if no links are found in the page.
        if not soup.find_all('a'):
            if verbose:
                logger.info("No links found on the page: %s. Switching to Selenium.", page_url)
            soup = get_html_with_selenium(page_url, verbose=verbose)

        if verbose:
            logger.info("Downloaded HTML from: %s", page_url)
        
        return str(soup)

    except HTTPError as err:
        if err.response.status_code in (403, 429):  # Forbidden or Too Many Requests
            if verbose:
                logger.info("Switching to Selenium due to HTTP error for: %s", page_url)
            soup = get_html_with_selenium(page_url, verbose=verbose)

            if verbose:
                logger.info("Downloaded HTML from: %s", page_url)
            
            return str(soup)

        if verbose:
            logger.info("HTTP error occurred for: %s. Skipping.", page_url)
        return None

    except InvalidSchema:
        if verbose:
            logger.info("Invalid URL schema: %s. Skipping.", page_url)
        return None

    except Exception as e:
        if verbose:
            logger.info("An error occurred when trying to download HTML from: %s. Error: %s. Skipping.", page_url, e)
        return None


def extract_linked_urls(html, page_url, verbose=False):
    """
    This function extracts all the URLs present in the HTML content and makes them absolute links by
    joining with the base_url if they are relative links. It only returns unique URLs.

    :param html: String containing the HTML content from which URLs are to be extracted.
    :param base_url: String containing the base URL for resolving relative links.
    :return: A set of unique URLs extracted from the HTML content.
    """

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        if verbose:
            logger.error("Error parsing HTML: %s", str(e), exc_info=True)
        return set()

    # Find all the anchor tags in the HTML and get the href attribute
    linked_urls = [link.get("href") for link in soup.find_all("a", href=lambda href: href and not href.endswith('.png'))]

    # Make URLs absolute by joining with the base_url. If the URL is already absolute, it will be returned as is.
    linked_urls = [urljoin(page_url, url) for url in linked_urls if url]

    # Get unique URLs by converting the list to a set
    linked_urls = set(linked_urls)

    # Remove the query parameters and fragment identifiers from the URLs
    clean_urls = set()
    for url in linked_urls:
        parsed_url = urlparse(url)
        clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", "", ""))
        clean_urls.add(clean_url)

    if verbose:
        logger.info(f"Found {len(clean_urls)} links in {page_url}")
        logger.info(clean_urls)

    return clean_urls

def scrape_domain(page_url, base_domain_url, max_workers=4, verbose=False):
    """
    This function performs the web scraping operation starting from the page_url, 
    it then continues to scrape all the linked pages within the same domain (base_domain_url).

    :param page_url: String containing the start URL to begin the scraping process.
    :param base_domain_url: String containing the base URL for resolving relative links.
    :return: Set containing URLs that have been scraped.
    """
    to_scrape_urls = set([page_url])
    scraped_urls = set()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        with tqdm(total=len(to_scrape_urls), desc="URLs processed") as pbar:
            while to_scrape_urls:
                # Pick a URL from the to_scrape_urls set and remove it from the set
                url = to_scrape_urls.pop()
                scraped_urls.add(url)
                
                future = executor.submit(download_html, url, verbose=verbose)
                html = future.result()
                if not html:
                    pbar.update(1)
                    continue

                urls = extract_linked_urls(html, url, verbose=verbose)

                # Saving the HTML content to S3
                future = executor.submit(upload_object, io.BytesIO(html.encode()), quote(url, safe="")+".html", verbose=verbose)

                for url in urls:
                    if base_domain_url not in url:  # Exclude URLs outside of the base domain
                        continue
                    if url in scraped_urls:  # Exclude URLs already scraped
                        continue
                    if url in to_scrape_urls:  # Exclude URLs already in the queue to be scraped
                        continue
                    if (len(scraped_urls)+len(to_scrape_urls)) > 1000:  # Limit the number of URLs to be scraped
                        continue

                    to_scrape_urls.add(url)
                    pbar.total += 1

                pbar.update(1)

    return scraped_urls


def scraping_bee_scrapper(url):
    client = ScrapingBeeClient(
        api_key=settings.scraping_bee_api_key)

    response = client.get(url)

    return response