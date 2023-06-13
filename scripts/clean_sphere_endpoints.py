import json
from services.helpers.logger import getLogger
from urllib.parse import urlparse, urlunparse

logger = getLogger()


def clean_sphere_endpoints(filename, local=False):
    with open(filename, 'r') as f:
        connectors = json.load(f)

    for connector in connectors:
        if connector['airbyte_status'] != 'lowcode-connector':
            logger.info(f"Skipping {connector['name']} because it is not a lowcode connector")
            continue

        cleaned_endpoints = []
        logger.info(f"Cleaning endpoints for {connector['name']}")
        for endpoint in connector['sphere_endpoints']:
            try:
                parsed_endpoint = urlparse(endpoint)
                # cleaned = parsed_endpoint._replace(query="", fragment="")
                cleaned = parsed_endpoint._replace(fragment="")
                cleaned = urlunparse(cleaned).rstrip('!?/.')
                cleaned = cleaned.split('?')
                if len(cleaned) > 1:
                    cleaned = f"{cleaned[0]}?param"
                else:
                    cleaned = cleaned[0]
                cleaned_endpoints.append(cleaned)
            except Exception as e:
                logger.info(f"{endpoint} is not a valid URL")

        connector['sphere_endpoints'] = list(set(cleaned_endpoints))
        connector['endpoint_count'] = len(connector['sphere_endpoints'])
        logger.info(f"Endpoints cleaned for {connector['name']}")

        with open(filename, 'w') as f:
            json.dump(connectors, f, indent=4)



if __name__ == '__main__':
    clean_sphere_endpoints('data/airbyte_lowcode_connectors.json', local=True)