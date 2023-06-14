import json
from services.helpers.logger import getLogger
from services.generators.requestor import predict_base_url

logger = getLogger()
filename = 'data/airbyte_lowcode_connectors.json'

with open(filename, 'r') as f:
    connectors = json.load(f)


for connector in connectors:
    filtered_endpoints = []

    # skip if not a lowcode connector
    if connector['airbyte_status'] != 'lowcode-connector':
        logger.info(f"Skipping {connector['name']} because it is not a lowcode connector")
        continue

    # skip if there are no sphere endpoints
    if not connector.get('sphere_endpoints', None):
        logger.info(f"Skipping {connector['name']} because it does not have endpoints")
        continue

    # predict the api base url
    logger.info(f"Predicting the api base url for {connector['name']}")
    api_base_url = predict_base_url(connector['base_url'], connector['sphere_endpoints'], connector['name'])
    logger.info(f"Predicted {api_base_url} for {connector['name']}")

    for endpoint in connector['sphere_endpoints']:
        # keep endpoints starting with /
        if endpoint.startswith('/'):
            filtered_endpoints.append(endpoint)
            continue

        # keep endpoints starting with the api base url
        if endpoint.startswith(api_base_url):
            filtered_endpoints.append(endpoint)
        

    # save the filtered endpoints and their count
    connector['filtered_sphere_endpoints'] = filtered_endpoints
    connector['filtered_sphere_endpoints_count'] = len(filtered_endpoints)

    with open('data/filtered_airbyte_connectors.json', 'w') as f:
        json.dump(connectors, f, indent=4)


