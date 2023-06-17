from services.helpers.s3 import read_object
from urllib.parse import quote
from collections import defaultdict
from services.helpers.logger import getLogger
from services.helpers.openai_gpt import completion
import inflect
import re
import json
import io

logger = getLogger()
p = inflect.engine()


prompt_examples = """
    Name: a single word that is the object being returned by this endpoint separated by underscore, all lowercase
    Parameters: an array of the parameters in the endpoint, assign empty array if there are no path and query parameters
    Schema: Define the endpoint response using the json draft 07 format, return an empty object if the information is not enough
"""


def generate_schemas(connector_name, connector_base_url, folder_name):
    # read bulk concise file from S3
    bulk_concise_content = read_object(f"{folder_name}/documentation.txt")

    if not bulk_concise_content:
        logger.info(f"No documentation file found for {connector_name}")
        return

    endpoints = read_object(f"{folder_name}/endpoints.txt")
    if not endpoints:
        logger.info(f"No endpoints found for {connector_name}")
        return

    endpoints = endpoints.split('\n')
    query_response_list = defaultdict(list)

    for endpoint in endpoints:
        matches = [m.start()
                   for m in re.finditer(r'{}(?!/)'.format(endpoint.rstrip('/')), bulk_concise_content)]

        if not matches:
            logger.info(f"No matches found for {endpoint}")
            continue

        # get the first two chunks only
        matches = matches[0:2]
        logger.info(f"Using {len(matches)}")

        # Calculate the length of each chunk
        chunk_length = 7000 // len(matches)
        before_after_endpoint = (chunk_length - len(endpoint)) // 2

        logger.info(f"Creating chunks for {endpoint}")
        endpoint_chunks = []
        for idx, match in enumerate(matches):
            start = 0 if match < before_after_endpoint else match - \
                100  # Start position of the chunk
            # End position of the chunk
            end = start + len(endpoint) + 100 + chunk_length
            chunk = bulk_concise_content[start:end]  # Get the chunk
            endpoint_chunks.append(chunk)

        query = f'''Describe the endpoint: {endpoint} in the following json object format only: {prompt_examples} using this information: {endpoint_chunks}. Return a single json object without extra information'''

        logger.info(f"Getting schema for {endpoint}")
        query_response = completion(query)
        try:
            query_response = json.loads(query_response)
        except Exception as e:
            logger.info(f"Could not load the response: {e}")
            query_response = None

        if query_response is not None and query_response['Name'] is not None:
            singular_object = p.singular_noun(
                query_response['Name'])
            if not singular_object:
                singular_object = query_response['Name']
            query_response_list[singular_object].append(
                query_response)
            logger.info(
                f"Added {query_response['Name']} to query response list")
        else:
            logger.info(f"No schema generated for {endpoint}")

    # now that all url responses are generated, save their files
    return query_response_list
