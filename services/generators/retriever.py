import json
import re
from urllib.parse import urlparse
import requests
import re
import yaml
import pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Pinecone
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from langchain.chains.question_answering import load_qa_chain
from services.helpers.logger import getLogger
from services.helpers.s3 import read_object
from services.helpers.config import settings


# Initialize Pinecone and OpenAI
pinecone.init(api_key=settings.pinecone_api_key,
              environment=settings.pinecone_env)
index_name = pinecone.Index(settings.pinecone_index_name)
ChatOpenAI.api_key = settings.openai_api_key
embeddings = OpenAIEmbeddings(openai_api_key=settings.openai_api_key)
llm = OpenAI(temperature=0, openai_api_key=settings.openai_api_key)
chain = load_qa_chain(llm, chain_type="stuff")

logger = getLogger()


# Function to load JSON data from a file
def load_json_from_file(filename):
    with open(filename, 'r') as file:
        return json.load(file)


# Function to load JSON data from S3
def load_json_from_s3(filename):
    file_content = read_object(filename)
    if file_content is None:
        return []
    return json.loads(file_content)


# Function to find the base URL given the domain base URL
def get_base_url(domain_base_url):
    query = "What is the most likely base url. Some endpoints include a version like /0/, /v0/. Give me the url (including https://) and nothing else"
    response = get_langchain_response(domain_base_url, query)

    if '/v1' in response:
        return response.split('/v1')[0] + '/v1'
    elif '/v2' in response:
        return response.split('/v2')[0] + '/v2'
    elif '/v3' in response:
        return response.split('/v3')[0] + '/v3'
    elif '/api' in response:
        return response.split('/api')[0] + '/api'
    elif '.com' in response:
        return response.split('.com')[0] + '.com'
    else:
        return response


# Function to find the best matching response from the options
def find_best_response(response, options):
    """Return the first matching response from the options, else 'None'."""
    response = response.lower()
    return next((option for option in options if option.lower() in response), 'None')


# Function to get the response from langchain for a given query
def get_langchain_response(domain_base_url, query):
    logger.info('Query: {}'.format(query))
    docsearch = Pinecone.from_existing_index(
        settings.pinecone_index_name, embeddings)
    docs = docsearch.similarity_search(
        query, k=5, filter={'domain_base_url': domain_base_url})
    response = chain.run(input_documents=docs, question=query)
    logger.info('Response: {}'.format(response))
    return response


# Function to identify the pagination strategy from the pagination response
def get_pagination_strategy(pagination_response):
    numbers = re.findall('\d+', pagination_response)
    page_size = int(numbers[-1]) if numbers else None
    if any(element in pagination_response for element in ['offset', 'offsetincrement']):
        return {
            "pagination_strategy": {"type": "OffsetIncrement", "page_size": page_size},
            "page_size_option": {"field_name": "limit"},
            "page_token_option": {"field_name": "offset"}
        }
    elif any(element in pagination_response for element in ['pageincrement']):
        return {
            "pagination_strategy": {"type": "PageIncrement", "page_size": page_size},
            "page_size_option": {"field_name": "per_page"},
            "page_token_option": {"field_name": "page"},
        }
    elif any(element in pagination_response for element in ['cursor']):
        return {
            "pagination_strategy": {"type": "CursorPagination", "page_size": page_size},
            "page_token_option": {"field_name": "from"},
        }
    return {}


# Function to get the pagination parameters for a base URL and domain
def get_pagination_parameters(base_url, domain):
    try:
        pagination_params_query = (
            f"This {base_url} uses pagination to fetch data. What are the main parameters? If main parameters contain 'page' or 'offset' ignore them"
            f"Just get the main parameter's name and return only one word parameter"
        )
        pagination_response = get_langchain_response(
            base_url, pagination_params_query)
        if pagination_response and "none" not in pagination_response.lower():
            return {"page_size_option": {
                "type": "RequestOption",
                "inject_into": "request_parameter",
                "field_name": pagination_response
            }}
        return {}
    except (ValueError, KeyError, Exception) as e:
        print(
            f"An error occurred while retrieving pagination parameters: {str(e)}")
        return {}


# Function to get the cursor pagination value from the cursor value response
def get_cursor_pagination_value(cursor_value_response):
    cursor_values = {
        "link": "{{headers.link.next.cursor}}",
        "cursor": "{{headers.link.next.cursor}}",
        "url": "{{headers['urls']['next']}}",
        "last record id": "{{last_records[-1]['id']}}",
    }
    return next((v for k, v in cursor_values.items() if k in cursor_value_response.lower()), "")


# Function to predict the paginator block given a base URL and domain
def predict_paginator_block(base_url, domain):
    try:
        pagination_query = (
            f"Identify the pagination strategy and the maximum page size based on the keywords found in this webpage: {base_url}."
            f"The strategy could be CursorPagination if 'cursor', 'link', 'next_token' are found, and "
            f"OffsetIncrement pagination if 'offset' is found, "
            f"PageIncrement pagination if 'page', 'page_size', 'pagesize', 'per_page', 'page_number', 'page number', 'pagenum' are found and "
            f"NoPagination pagination if any of above key words is not found "
            f"Once the strategy and max page size are identified, just provide the pagination strategy and page size."
        )

        pagination_response = get_langchain_response(
            base_url, pagination_query)

        paginator_json = {
            "type": "DefaultPaginator",
            "page_size_option": {
                "inject_into": "request_parameter",
                "field_name": "",
            },
            "pagination_strategy": {
                "type": "",
                "page_size": ""
            },
            "page_token_option": {
                "type": "RequestOption",
                "inject_into": "request_parameter",
                "field_name": "",
            },
        }
        pagination_strategy = get_pagination_strategy(
            pagination_response.lower())

        if pagination_strategy is None:
            return {"type": "NoPagination"}

        paginator_json["pagination_strategy"].update(
            pagination_strategy["pagination_strategy"])
        paginator_json["page_token_option"].update(
            pagination_strategy["page_token_option"])

        strategy_type = pagination_strategy["pagination_strategy"]["type"]
        if strategy_type in ["OffsetIncrement", "PageIncrement"]:
            paginator_json.update(
                get_pagination_parameters(base_url, domain))

        if strategy_type == "CursorPagination":
            cursor_value_query = (
                f"This url {base_url} uses cursor pagination."
                f"I want to know, On what basis it makes further request to fetch the next data"
                f"either it uses next url in headers, last record id in parameter or next cursor link?"
                f"Just tell me the method it uses and don't add extra text"
            )
            cursor_value_response = get_langchain_response(
                base_url, cursor_value_query)
            paginator_json["pagination_strategy"]["cursor_value"] = get_cursor_pagination_value(
                cursor_value_response)

        return paginator_json
    except Exception as e:
        logger.error(
            f"Something went wrong while getting pagination type: {e}")
        return {"type": "NoPagination"}


# Function to predict the record selector block given a base URL and domain
def predict_record_selector_block(base_url, domain):
    try:
        record_selector_query = (
            f"Record Selector objects defines what data the API returns when fetching resources."
            f"I want the type of the extractor of the record selector used for the URL {domain} to fetch the data."
            f"The extractor type may be the 'None' or 'DpathExtractor'."
            f"Don't add any extra text, just tell extractor type being used in record selector extractor"
        )
        record_selector_response = get_langchain_response(
            base_url, record_selector_query)
        record_selector_json = {
            "type": "RecordSelector",
            "extractor": {
                "field_path": ["data"]
            },
        }

        if record_selector_response and 'None' not in record_selector_response:
            record_selector_json["extractor"].update(
                {"type": "DpathExtractor"})

        extractor_field_path_query = (
            f"Based on the api calls of this {base_url}, can you infer the extractor "
            f"field_paths in the record_selector block of the source connector? Please provide a list of likely "
            f"field_paths that can efficiently translate an HTTP response into a list of records."
            f"Just give me a list of record extractor field_path inside '[]' or '[]' and don't add extra text"
        )

        extractor_field_path = get_langchain_response(
            base_url, extractor_field_path_query)
        if extractor_field_path:
            match = re.findall(r"\[.*?\]", extractor_field_path)
            path_list = json.loads(match[0]) if match else []
            record_selector_json["extractor"]["field_path"] = path_list

        return record_selector_json
    except Exception as e:
        logger.error(
            f"Something went wrong while getting record selector type: {e}")
        return {"type": "RecordSelector", "extractor": {"field_path": ["data"]}, }


# Function to extract the sphere retriever block given a connector
def extract_sphere_retriever_block(connector):
    base_url = (connector['base_url']).strip()

    domain = urlparse(base_url).netloc

    record_selector_object = predict_record_selector_block(base_url, domain)
    pagination_object = predict_paginator_block(base_url, domain)
    retriever_block = {
        "type": "SimpleRetriever",
                "record_selector": record_selector_object,
                "paginator": pagination_object,
                "requester": {"$ref": "#/definitions/requester"}
    }
    return retriever_block


# Recursive function to find the block in the Airbyte data
def find_block(data, block_name):
    if isinstance(data, dict):
        if block_name in data:
            return data[block_name]
        for key, value in data.items():
            block = find_block(value, block_name)
            if block is not None:
                return block
    elif isinstance(data, list):
        for item in data:
            block = find_block(item, block_name)
            if block is not None:
                return block
    return None


def set_block_by_path(document, path, value):
    block = document
    for key in path[:-1]:
        block = block[key]
    block[path[-1]] = value


# Function to extract the Airbyte retriever block given a connector name
def extract_airbyte_retriever_block(connector_name):
    connector_name = connector_name.lower()

    connector_folder_name = connector_name.replace(" ", "-").replace("_", "-")
    connector_file_name = connector_folder_name.replace('-', '_')

    url = f"https://raw.githubusercontent.com/airbytehq/airbyte/master/airbyte-integrations/connectors/source-{connector_folder_name}/source_{connector_file_name}/manifest.yaml"

    response = requests.get(url)

    if response.status_code == 200:
        try:
            data = yaml.safe_load(response.text)
            retriever_block = find_block(data, 'retriever')
            record_selector_block = find_block(
                retriever_block, 'record_selector')
            paginator_block = find_block(
                retriever_block, 'paginator')

            if '$ref' in record_selector_block:
                ref_path = record_selector_block['$ref'].split('/')[-1]
                ref_block = find_block(data, ref_path)
                set_block_by_path(retriever_block, [
                                  'record_selector'], ref_block)

            if '$ref' in paginator_block:
                ref_path = paginator_block['$ref'].split('/')[-1]
                ref_block = find_block(data, ref_path)
                set_block_by_path(retriever_block, ['paginator'], ref_block)

            return retriever_block if retriever_block is not None else {}
        except Exception as e:
            return {}
    else:
        logger.error('\nFailed to fetch file for {}, status code: {}'.format(
            connector_name, response.status_code))
        return {}


# Function to flatten a json object for comparison
def json_flatten(json_object, delimiter="."):
    out = {}

    def flatten(x, name=""):
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + delimiter)
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + delimiter)
                i += 1
        else:
            out[name[:-1]] = x

    flatten(json_object)
    return out


# Function to calculate the similarity percentage between two JSON blocks
def calculate_line_similarity(airbyte_block, sphere_block):

    # Flattening json objects and getting key-value pairs
    airbyte_block_key_value_pair = list(json_flatten(airbyte_block).items())
    sphere_block_key_value_pair = list(json_flatten(sphere_block).items())

    # Counting matches
    matches = len(set(airbyte_block_key_value_pair).intersection(
        sphere_block_key_value_pair))
    similarity = (matches / len(airbyte_block_key_value_pair)) * \
        100 if len(airbyte_block_key_value_pair) != 0 else matches
    return round(similarity, 2), matches, len(airbyte_block_key_value_pair)


# Main function to process connectors and calculate the retriever block similarities
def main(filename, local=False):
    connectors = load_json_from_file(
        filename) if local else load_json_from_s3(filename)

    retrievers_comparison = {}
    total_matches = 0
    total_airbyte_block_pair_count = 0

    for connector in connectors:
        if connector.get('airbyte_status') != 'lowcode-connector':
            continue

        airbyte_retriever_block = extract_airbyte_retriever_block(
            connector['name'])
        sphere_retriever_block = extract_sphere_retriever_block(connector)
        retriever_block_similarity, matches_count, airbyte_block_pair_count = calculate_line_similarity(
            airbyte_retriever_block, sphere_retriever_block)
        total_matches = total_matches + matches_count
        total_airbyte_block_pair_count = total_airbyte_block_pair_count + \
            airbyte_block_pair_count
        retrievers_comparison[connector['name']] = {
            'airbyte_retriever_block': airbyte_retriever_block,
            'sphere_retriever_block': sphere_retriever_block,
            'similarity': retriever_block_similarity
        }

        logger.info("Processed connector: {}".format(connector['name']))

    overall_similarity = (total_matches/total_airbyte_block_pair_count) * \
        100 if total_airbyte_block_pair_count != 0 else total_matches

    with open('connectors_retriever_blocks.json', 'w') as f:
        json.dump({"overall_similarity": round(overall_similarity, 2),
                  "retrievers": retrievers_comparison}, f, indent=4)


if __name__ == "__main__":
    main('data/airbyte_connectors.json', local=True)
