import json
import re
from services.helpers.logger import getLogger

logger = getLogger()
filename = 'airbyte_connectors.json'

with open(filename, 'r') as f:
    connectors = json.load(f)

filtered_connectors = []

for connector in connectors:
    if connector['airbyte_status'] != 'lowcode-connector':
        logger.info(f"Skipping {connector['name']} because it is not a lowcode connector")
        continue

    if not connector.get('sphere_endpoints', None):
        logger.info(f"Skipping {connector['name']} because it does not have endpoints")
        continue

    # base_url_components = list(filter(None, re.split('\.|-|/',connector['base_url'])))
    base_url_components = list(filter(lambda x: x not in ['https:', 'www', 'com', ''], re.split('\.|-|/',connector['base_url'])))
    logger.info(f"Split base url for {connector['name']}: {base_url_components}")

    filtered_urls = []

    for endpoint in connector['sphere_endpoints']:
        if endpoint.endswith(('.jpg', '.png', '.jpeg', '.gif', '.ico')):
            continue

        if endpoint.startswith('/'):
            filtered_urls.append(endpoint)
            continue

        has_base_url_substring = any(substr in endpoint for substr in base_url_components)
        if has_base_url_substring:
            filtered_urls.append(endpoint)

    connector['filtered_endpoints'] = filtered_urls
    connector['filtered_endpoints_count'] = len(filtered_urls)
    connector['filtered_out'] = [element for element in connector['sphere_endpoints'] if element not in connector['filtered_endpoints']]
    connector['filtered_out_count'] = len(connector['filtered_out'])

    filtered_connectors.append(connector)

    logger.info(f"{len(filtered_urls)} for {connector['name']}")

    with open('filtered_airbyte_connectors.json', 'w') as f:
        json.dump(filtered_connectors, f, indent=4)


