from services.helpers.s3 import read_object, upload_object, list_objects
from urllib.parse import quote
from services.helpers.logger import getLogger
import json
import html2text
import io
from services.scrapers.domain_processor import convert_html_to_md
from services.scrapers.link_matcher import detect_links
from termcolor import colored
from collections import OrderedDict

logger = getLogger()



def create_md_files(filename, local=False):
    if local:
        with open(filename, 'r') as f:
            connectors = json.load(f)
    else:
        file_content = read_object(filename)
        connectors = json.loads(file_content)

    for connector in connectors:
        page_count = connector.get('scraped_page_count', None)
        if not page_count or connector['airbyte_status'] != 'lowcode-connector':
            logger.info("No pages scrapped for {}".format(connector['name']))
            continue
        logger.info("Creating md files for {}".format(connector['name']))
        base_url = connector['base_url']
        quoted_base_url = quote(base_url, safe="")
        file_keys = list_objects([quoted_base_url, ".html"])

        combined_file_content = ''
        for file_key in file_keys:
            logger.info("Generating .md file for {}".format(file_key))
            file_content = convert_html_to_md(read_object(file_key))
            upload_object(io.BytesIO(file_content.encode('utf-8')),
                          file_key.rsplit('.html', 1)[0] + ".md")
            combined_file_content += file_content + "\n"

        upload_object(io.BytesIO(combined_file_content.encode(
            'utf-8')), quoted_base_url + '-bulk' + '.md')

        # this code splits the text to paragraphs then converts to ordereddict to ensure uniqueness and keep the correct order
        paragraphs = combined_file_content.split("\n\n")
        ordered_dict = OrderedDict.fromkeys(paragraphs)
        unique_paragraphs = list(ordered_dict.keys())
        upload_object(io.BytesIO("\n\n".join(unique_paragraphs).encode(
            'utf-8')), quoted_base_url + '-bulk-concise' + '.md')

        logger.info(f"Uploaded concise bulk for {connector['name']}")


# Usage:
if __name__ == "__main__":
    create_md_files('airbyte_connectors.json', local=True)
