import json
import os
import random
import time
from urllib.parse import urlparse
import requests
import yaml
import pinecone
import openai
import re

from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Pinecone
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI
from langchain.chains.question_answering import load_qa_chain

from services.helpers.logger import getLogger
from services.helpers.s3 import read_object
from services.helpers.config import settings


# Initialize Pinecone and OpenAI
openai.api_key = settings.openai_api_key
pinecone.init(api_key=settings.pinecone_api_key,
              environment=settings.pinecone_env)
index_name = pinecone.Index(settings.pinecone_index_name)
ChatOpenAI.api_key = settings.openai_api_key
embeddings = OpenAIEmbeddings(openai_api_key=settings.openai_api_key)
llm = OpenAI(temperature=0, openai_api_key=settings.openai_api_key)
chain = load_qa_chain(llm, chain_type="stuff")

logger = getLogger()
AIRBYTE_MASTER_URL = "https://raw.githubusercontent.com/airbytehq/airbyte/master/airbyte-integrations/connectors"


def load_json_from_file(filename):
    with open(filename, 'r') as file:
        return json.load(file)


def load_json_from_s3(filename):
    file_content = read_object(filename)
    if file_content is None:
        return []
    return json.loads(file_content)


def predict_base_url(domain_base_url, endpoints, connector_name):
    # query = "What is the most likely base url. Some endpoints include a version like /0/, /v0/. Give me the url (including https://) and nothing else"
    # query = "What is the most likely base url of the apis. Base urls exist in most of the apis. Some apis include /v1, /v0, /api in it. Give me the exact base url"
    query = f"Give me the part of URL from start (base URL) which is common in start of  the most of the given API URLs. Give me only one url (including https://) and nothing else: {str(endpoints)}"
    response = get_completion_response(query)
    parsed_url = urlparse(response)
    return f"{parsed_url.scheme}://{parsed_url.netloc}"


def find_best_response(response, options):
    """Return the first matching response from the options, else 'None'."""
    return next((option for option in options if option.lower() in response.lower()), 'None')


def get_langchain_response(domain_base_url, query):
    try:
        query = query + ". Return 'None' if don't find any response"
        # logger.info('Query: {}'.format(query))
        docsearch = Pinecone.from_existing_index(
            settings.pinecone_index_name, embeddings)
        docs = docsearch.similarity_search(
            query, k=5, filter={'domain_base_url': domain_base_url})
        response = chain.run(input_documents=docs, question=query)
        # logger.info('Response: {}'.format(response))
        return response.strip()
    except Exception as e:
        logger.error('Error in get_langchain_response: {}'.format(e))
        return None


def get_completion_response(query):
    max_retries = 5
    query = query[:6000]
    for attempt in range(max_retries):
        try:
            response = openai.ChatCompletion.create(
                model='gpt-3.5-turbo',
                messages=[
                    {"role": "user", "content": query},
                ]
            )
            return response['choices'][0]['message']['content']

        except openai.error.RateLimitError:
            wait_time = (2 ** attempt) + random.random()
            logger.error(
                f"Request exceeded rate limit. Waiting {wait_time} seconds before retrying.")
            time.sleep(wait_time)

    raise Exception(f"Maximum number of retries ({max_retries}) exceeded.")


def predict_sub_authentication_type(base_url, domain_base_url, authentication_type):
    if authentication_type == "BasicHttpAuthenticator":
        return {
            "type": "BasicHttpAuthenticator",
            "username": "{{config.username}}",
            "password": "{{config.password}}"
        }
    elif authentication_type == "BearerAuthenticator":
        return {
            "type": "BearerAuthenticator",
            "api_token": "{{config.api_token}}",
        }
    elif authentication_type == 'ApiKeyAuthenticator':
        query = f"Give me the header name which should be present to authorize the API call with base URL {base_url}? Header names are usually (Authorization, ApiKey, Username etc.) Give me the one word header name and don't add extra text"
        response = get_langchain_response(domain_base_url, query)
        return {
            'type': authentication_type,
            "api_token": "{{config.api_token}}",
            "header": response,
        }
    elif authentication_type == 'OAuth':
        query = f"What is the endpoint to refresh the access token for the API endpoints having base url starts with URL: {base_url}? Give me the exact endpoint and don't add extra text"
        response = get_langchain_response(domain_base_url, query)
        response = {
            'type': authentication_type,
            'token_refresh_endpoint': response,
            'client_id': '{{config.client_id}}',
            'client_secret': '{{config.client_secret}}',
            'refresh_token': '{{config.refresh_token}}'
        }
        return response
    else:
        return {'type': authentication_type}


def predict_authenticator_block(base_url, domain_base_url):
    authenticator_options = [
        "BasicHttpAuthenticator",
        "BearerAuthenticator",
        "ApiKeyAuthenticator",
        "OAuth"
    ]
    # query = "What is the method of authentication to authorize the API calls with this API? Following are the options: {authenticator_options}. BasicHttpAuthenticator if basic auth keywords exist. BearerHttpAuthenticator if Bearer or Authorization keywords exist. ApiKeyAuthenticator if API or Authorization keywords exist. Return the response from given options, just return the one word option which is the most relevant"
    query = f"What is the method of authentication to authorize the API calls with this API? Following are the options: {authenticator_options}. Return the response from given options, just return the one word option"
    langchain_response = get_langchain_response(domain_base_url, query)
    authentication_type = find_best_response(
        langchain_response, authenticator_options)
    response = predict_sub_authentication_type(
        base_url, domain_base_url, authentication_type)

    return response


def remove_special_characters(input_string):
    special_characters = "!@#$%^&*()[]{};:,./<>?\|`~-=_+'\" "
    return input_string.strip(special_characters)


def predict_request_headers(base_url, domain_base_url, endpoints):
    ignored_headers = ["Accept-Language", "Authorization", "Content-Type", "User-Agent", "Accept", "Link", "None"]

    # query = f"Which Headers are required to be present in the request for the apis of this base url's {base_url} endpoints. Return the name of headers in a list if they are required and if no header is required return 'None'"
    query = f"Given the following list of endpoints, which headers should be present in request for these endpoint apis with base url {base_url}. Give me the required headers names separated on comma(,) basis. If no header is required, return None: {str(endpoints[:100])}"
    langchain_response = get_langchain_response(domain_base_url, query)

    if langchain_response != "None" and langchain_response != None:
        headers_list = []
        filtered_headers_list = []
        if ":" in langchain_response:
            formatted_header = re.findall(r"([^,:]+):", langchain_response)
            headers_list = [header.strip() for header in formatted_header if len(header.strip().split(" ")) == 1]
        else:
            headers_list = [header.strip() for header in langchain_response.split(",") if len(header.strip().split(" ")) == 1]
        filtered_headers_list = [remove_special_characters(header) for header in headers_list if header not in ignored_headers]

        return filtered_headers_list
    else:
        return None


def predict_request_parameters(base_url, domain_base_url, endpoints):
    ignored_query_params = ["limit","from", "cursor", "email", "name", "api_key", "page", "offset", "None", "per_page"]
    
    query = f"There are two types of request parameters. One is 'headers'(these parameters are hidden in request headers) and other is 'query'(these parameters are present in the url with '?' and '=' key values) parameters. Ignore the 'header' parameters. What are major query parameters that should be present in request parameter when APIs with this base url: '{base_url}' used to fetch the data. Only give the query parameters names and separate them on the basis of comma(,)"
    # query = f"What are major query parameters that should be present in request parameter when APIs with this base url: '{base_url}' used to fetch the data consider that we are skipping headers parameters and looking for only query parameters"
    langchain_response = get_langchain_response(domain_base_url, query)

    if langchain_response != "None" and langchain_response != None:
        parameters_list = None
        if ":" in langchain_response:
            formatted_parameters = re.findall(r"([^,:]+):", langchain_response)
            parameters_list = [parameter.strip() for parameter in formatted_parameters if len(parameter.strip().split(" ")) == 1]
        else:
            parameters_list = [parameter.strip() for parameter in langchain_response.split(",") if len(parameter.strip().split(" ")) == 1]
        params_without_ids = [parameter for parameter in parameters_list if not parameter.endswith('Id') and not parameter.endswith('id')]
        filtered_parameters_list = [remove_special_characters(parameter) for parameter in params_without_ids if parameter not in ignored_query_params]

        return filtered_parameters_list
    else:
        return None


def update_error_handler_object(error_handler_obj, status_codes, http_codes, action):
    """Update error handler object with provided codes and action if the codes exist in the status codes."""
    matching_codes = [code for code in http_codes if code in status_codes]
    if matching_codes:
        error_handler_obj["error_handlers"].append({
            "type": "DefaultErrorHandler",
            "response_filters": [{
                "http_codes": matching_codes,
                "action": action
            }]
        })
        return True
    return False


def predict_error_handler_block(base_url, domain_base_url):
    """Predicts error handler block."""
    query = f"What are the possible HTTP status codes for the APIs having this base url: '{base_url}'"
    langchain_response = get_langchain_response(domain_base_url, query)

    if langchain_response == "None":
        return None

    status_codes = [int(code) for code in re.findall(r'\d+', langchain_response)]
    error_handler_obj = {
        "type": "CompositeErrorHandler",
        "error_handlers": []
    }

    error_handler_updated = any([
        update_error_handler_object(error_handler_obj, status_codes, [403], "IGNORE"),
        update_error_handler_object(error_handler_obj, status_codes, [429, 500], "RETRY")
    ])
    
    if error_handler_updated:
        return error_handler_obj

    return None


def predict_requester_block(connector):
    base_url = predict_base_url(connector['base_url'], connector['sphere_endpoints'], connector['name'])
    authenticator = predict_authenticator_block(base_url, connector['base_url'])
    request_headers = predict_request_headers(base_url, connector['base_url'], connector['sphere_endpoints'])
    request_parameters = predict_request_parameters(base_url, connector['base_url'], connector['sphere_endpoints'])
    # error_handler = predict_error_handler_block(base_url, connector['base_url'])
    requester_block = {
        "type": "HttpRequester",
        "url_base": base_url.strip(),
        "http_method": "GET",
        "authenticator": authenticator,
    }

    if request_headers is not None and len(request_headers) > 0:
        header_parameters = {}
        for header in request_headers:
            header_parameters[header.lower()] = "{{config." + header.lower().replace('-','_') + "}}"

        requester_block["request_headers"] = header_parameters

    if request_parameters is not None and len(request_parameters) > 0:
        request_parameters_block = {}
        for parameter in request_parameters:
            request_parameters_block[parameter.lower()] = "{{config." + parameter.lower().replace('-','_') + "}}"

        requester_block["request_parameters"] = request_parameters_block

    # if error_handler is not None:
    #     requester_block["error_handler"] = error_handler

    return requester_block


def normalize_airbyte_requester_block(json_obj):
    def traverse(obj):
        if isinstance(obj, dict):
            for k in list(obj.keys()):
                v = obj[k]
                if k == 'error_handler':
                    del obj[k]
                elif isinstance(v, str) and 'config' in v:
                    obj[k] = "{{config." + k.lower().replace('-', '_') + "}}"
                elif k == 'url_base':
                    parsed_url = urlparse(v)
                    obj[k] = f"{parsed_url.scheme}://{parsed_url.netloc}"
                else:
                    traverse(v)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)
    traverse(json_obj)
    return json_obj


def find_airbyte_requester_block(data):
    if isinstance(data, dict):
        if 'requester' in data:
            return data['requester']
        for key, value in data.items():
            auth_block = find_airbyte_requester_block(value)
            if auth_block is not None:
                return auth_block
    elif isinstance(data, list):
        for item in data:
            auth_block = find_airbyte_requester_block(item)
            if auth_block is not None:
                return auth_block
    return None


def extract_airbyte_requester_block(connector_name):
    connector_name = connector_name.lower().replace(" ", "-").replace("_", "-")
    connector_file_name = connector_name.replace('-', '_')

    url = f"{AIRBYTE_MASTER_URL}/source-{connector_name}/source_{connector_file_name}/manifest.yaml"

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        logger.error(
            f'Failed to fetch file for {connector_name}, status code: {response.status_code}')
        return {}

    try:
        data = yaml.safe_load(response.text)
        requester_block = find_airbyte_requester_block(data)
        consistent_requester_block = normalize_airbyte_requester_block(requester_block)
        return consistent_requester_block if consistent_requester_block is not None else {}
    except Exception as e:
        return {}


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


def calculate_line_similarity(airbyte_block, sphere_block):
    airbyte_block_key_value_pair = list(json_flatten(airbyte_block).items())
    sphere_block_key_value_pair = list(json_flatten(sphere_block).items())

    matches = len(set(airbyte_block_key_value_pair).intersection(
        sphere_block_key_value_pair))
    similarity = (matches / len(airbyte_block_key_value_pair)) * \
        100 if len(airbyte_block_key_value_pair) != 0 else matches
    return round(similarity, 2), matches, len(airbyte_block_key_value_pair)


def main(filename, local=False):
    connectors = load_json_from_file(
        filename) if local else load_json_from_s3(filename)

    requesters_comparison = {}
    total_matches = 0
    total_airbyte_block_pair_count = 0

    for idx, connector in enumerate(connectors):
        if connector.get('airbyte_status') != 'lowcode-connector':
            continue

        airbyte_requester_block = extract_airbyte_requester_block(
            connector['name'])
        sphere_requester_block = predict_requester_block(connector)
        
        requester_block_similarity, matches_count, airbyte_block_pair_count = calculate_line_similarity(
            airbyte_requester_block, sphere_requester_block)
        requesters_comparison[connector['name']] = {
            'airbyte_requester_block': airbyte_requester_block,
            'sphere_requester_block': sphere_requester_block,
            'similarity': requester_block_similarity,
        }

        total_matches += matches_count
        total_airbyte_block_pair_count += airbyte_block_pair_count
        logger.info("Processed connector {}: {}".format(idx+1, connector['name']))

    overall_similarity = (total_matches/total_airbyte_block_pair_count) * \
        100 if total_airbyte_block_pair_count != 0 else total_matches

    if not os.path.exists('data'):
        os.makedirs('data')
    with open('data/requesters_comparison.json', 'w') as f:
        json.dump({"overall_similarity": round(overall_similarity, 2),
                  "requesters": requesters_comparison}, f, indent=4)

if __name__ == "__main__":
    main('data/airbyte_lowcode_connectors.json', local=True)