import re
from services.helpers.s3 import read_object, upload_object
from services.helpers.logger import getLogger
import json
import io

logger = getLogger()


def compare_lowcode_endpoints(filename, local=False):
    lowcode_connectors = []
    regex_pattern = r'({{.*?}}|{.*?}|<.*?>)'
    replace_argument_pattern = r"<[^>]+>|{[^{}]+}|{{[^{}]+}}|:[^/}]+"

    if local:
        with open(filename, 'r') as f:
            connectors = json.load(f)
    else:
        file_content = read_object(filename)
        connectors = json.loads(file_content)

    # new_set = []
    for connector in connectors:
        if connector['airbyte_status'] != 'lowcode-connector':
            logger.info(f"Skipping {connector['name']}, not a lowcode connector")
            continue

        #  makes sure that the list of Airbyte existing endpoints exists
        if connector.get('sphere_endpoints', None) == None:
            logger.info(f"{connector['name']} does not have a list of existing Airbyte endpoints")
            continue

        # makes sure that the list of Sphere endpoints isn't empty (dynamic if empty)
        if not connector['sphere_endpoints'] and connector['scraped_page_count'] == 1:
            logger.info(f"{connector['name']} has an empty list of Sphere endpoints and 1 scraped page, it must be a dynamic JS page")
            continue

        # makes sure that the list of Airbyte existing endpoints exists
        if not connector.get('existing_airbyte_endpoints', None):
            logger.info(f"{connector['name']} does not have a list of existing Airbyte endpoints")
            continue

        # perform comparison
        common_endpoints = []
        connector['sphere_endpoints'] = [re.sub(replace_argument_pattern, 'param', url) for url in connector['sphere_endpoints']]
        connector['existing_airbyte_endpoints'] = [re.sub(replace_argument_pattern, 'param', url) for url in connector['existing_airbyte_endpoints']]
        for idx, airbyte_endpoint in enumerate(connector['existing_airbyte_endpoints']):
            split_airbyte_endpoint = airbyte_endpoint.split('?')
            if len(split_airbyte_endpoint) > 1:
                connector['existing_airbyte_endpoints'][idx] = f"{split_airbyte_endpoint[0]}?param"

        # new_set.append({'sphere_endpoints': sphere_endpoints, 'existing_airbyte_endpoints': existing_airbyte_endpoints})

        # with open('data/test_replacement.json', 'w') as f:
        #     json.dump(new_set, f, indent=4)
        logger.info(f"Extracting common endpoints for {connector['name']}")
        # Check if both 'existing_airbyte_endpoints' and 'sphere_endpoints' exist in the connector
        if 'existing_airbyte_endpoints' in connector and 'sphere_endpoints' in connector:
            # For each airbyte endpoint, check if it is included in any sphere endpoint
            for airbyte_endpoint in connector['existing_airbyte_endpoints']:
                airbyte_endpoint_norm = re.sub(regex_pattern, '{variable}', airbyte_endpoint)
                for sphere_endpoint in connector['sphere_endpoints']:

                    if re.sub(regex_pattern, '{variable}', sphere_endpoint).endswith(airbyte_endpoint_norm):
                        common_endpoints.append(airbyte_endpoint)
                        break  # Break out of the inner loop if a match is found

        # # For each airbyte endpoint, check if it is included in any sphere endpoint
        # for airbyte_endpoint in existing_airbyte_endpoints:
        #     airbyte_endpoint_norm = re.sub(regex_pattern, '{variable}', airbyte_endpoint)
        #     for sphere_endpoint in sphere_endpoints:

        #         if re.sub(regex_pattern, '{variable}', sphere_endpoint).endswith(airbyte_endpoint_norm):
        #             common_endpoints.append(airbyte_endpoint)
        #             break  # Break out of the inner loop if a match is found


        connector['common_endpoints'] = common_endpoints
        connector['common_endpoint_count'] = len(common_endpoints)

        logger.info(f"Found {len(connector['common_endpoints'])} common endpoints for {connector['name']}")

        # add this connector to a new list of connectors
        lowcode_connectors.append(connector)

    logger.info(f"Writing connectors to json file")
    if local:
        with open('data/lowcode_connectors_comparison.json', 'w') as f:
            json.dump(lowcode_connectors, f, indent=4)
    else:
        updated_connectors = json.dumps(connectors, indent=4)
        file_obj = io.BytesIO(updated_connectors.encode('utf-8'))
        upload_object(file_obj, filename, extraArgs={'CacheControl': 'no-store'})


if __name__ == "__main__":
    compare_lowcode_endpoints('data/airbyte_lowcode_connectors.json', local=True)