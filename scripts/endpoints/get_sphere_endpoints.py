from services.scrapers.link_matcher import detect_links
from services.helpers.s3 import read_object, upload_object, list_objects
import json
from services.helpers.logger import getLogger
from urllib.parse import quote
import io

logger = getLogger()


def recreate_sphere_endpoints(filename):
    file_content = read_object(filename)
    connectors = json.loads(file_content)

    # read lowcode only file
    logger.info("Reading lowcode connectors json file")
    file_content = read_object('airbyte_lowcode_connectors.json')
    airbyte_lowcode_connectors = json.loads(file_content)

    for connector in connectors:
        if connector['airbyte_status'] != 'lowcode-connector':
            logger.info(f"Skipping {connector['name']} because it is not lowcode")
            continue

        logger.info(f"Getting endpoints for {connector['name']}")

        # read concise bulk file
        quoted_base_url = quote(connector['base_url'], safe="")
        bulk_concise_file = read_object(f"{quoted_base_url}-bulk-concise.md")

        # split into paragraphs
        paragraphs = bulk_concise_file.split("\n\n")

        extracted_links = []
        for paragraph in paragraphs:
            links = detect_links(paragraph)
            extracted_links.extend(links)

        extracted_links = list(set(extracted_links))
        connector['endpoint_count'] = len(extracted_links)
        connector['sphere_endpoints'] = extracted_links
        logger.info(f"Extracted {len(extracted_links)} link for {connector['name']}")
        
        updated_connectors = json.dumps(connectors, indent=4)
        file_obj = io.BytesIO(updated_connectors.encode('utf-8'))
        upload_object(file_obj, filename, extraArgs={'CacheControl': 'no-store'})
        logger.info(f"Updated {filename} for {connector['name']}")

        index = next((i for i, obj in enumerate(airbyte_lowcode_connectors) if obj["name"] == connector["name"]), None)
        if index is not None:
            airbyte_lowcode_connectors[index] = connector
            logger.info(f"Found index {index} for {connector['name']}")
        else:
            airbyte_lowcode_connectors.append(connector)
            logger.info(f"Added {connector['name']} to list")

        logger.info(f"Updating lowcode connector file for {connector['name']}")
        updated_lowcode_connectors = json.dumps(airbyte_lowcode_connectors, indent=4)
        file_obj = io.BytesIO(updated_lowcode_connectors.encode('utf-8'))
        upload_object(file_obj,'airbyte_lowcode_connectors.json')


if __name__ == "__main__":
    recreate_sphere_endpoints('airbyte_connectors.json')