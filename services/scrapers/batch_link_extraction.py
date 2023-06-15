from services.helpers.s3 import read_object, upload_object
from urllib.parse import quote
from services.helpers.logger import getLogger
from services.generators.smart_search import smart_search_new_new, detect_get
import json
import io

logger = getLogger()


def extract_links(filename, local=False):
    if local:
        with open(filename, 'r') as f:
            connectors = json.load(f)
    else:
        file_content = read_object(filename)
        connectors = json.loads(file_content)

    for connector in connectors:
        # get the bulk concise file for connector
        quoted_base_url = quote(connector['base_url'], safe="")
        logger.info(f"Reading bulk concise of {connector['name']}")
        bulk_concise_contents = read_object(
            f"{quoted_base_url}-bulk-concise.md")

        logger.info(f"Extracting links for {connector['name']}")
        # extract links using smart_search and update the connector
        extracted_links = list(set(smart_search_new_new(
            detect_get, bulk_concise_contents, connector)))
        connector['endpoint_count'] = len(extracted_links)
        connector['sphere_endpoints'] = extracted_links

        logger.info(f"Extracted {connector['endpoint_count']} links for {connector['name']}")

        if local:
            with open(filename, 'w') as f:
                json.dump(connectors, f, indent=4)
        else:
            updated_connectors = json.dumps(connectors, indent=4)
            file_obj = io.BytesIO(updated_connectors.encode('utf-8'))
            upload_object(file_obj, filename, extraArgs={
                          'CacheControl': 'no-store'})


if __name__ == "__main__":
    extract_links('data/airbyte_lowcode_connectors.json', local=True)
