import json
import os
import requests
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
AIRBYTE_MASTER_URL = "https://raw.githubusercontent.com/airbytehq/airbyte/master/airbyte-integrations/connectors"


def load_json_from_file(filename):
    with open(filename, 'r') as file:
        return json.load(file)


def load_json_from_s3(filename):
    file_content = read_object(filename)
    if file_content is None:
        return []
    return json.loads(file_content)


def predict_base_url(domain_base_url, endpoints):
    # query = "What is the most likely base url. Some endpoints include a version like /0/, /v0/. Give me the url (including https://) and nothing else"
    # query = "What is the most likely base url of the apis. Base urls exist in most of the apis. Some apis include /v1, /v0, /api in it. Give me the exact base url"
    query = f"Given the following list of endpoints what is the most likely base url. Some endpoints include a version like '/v0', '/v1'. Give me the url (including https://) and nothing else: {str(endpoints)}"
    response = get_llm_response(query)
    URL_PARTS = ['/v0', '/v1', '/v2', '/v3']
    for part in URL_PARTS:
        if part in response:
            return response.split(part)[0]
    return response.rstrip('/')


def find_best_response(response, options):
    """Return the first matching response from the options, else 'None'."""
    response = response.lower()
    return next((option for option in options if option.lower() in response), 'None')


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
    except Exception as e:
        logger.error('Error in get_langchain_response: {}'.format(e))
    return response


def get_llm_response(query):
    query = query[:6000]
    response = llm(query)
    return response.strip('\n')


def predict_sub_authenticator_block(base_url, domain_base_url, authentication_type):
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
        query = f"What is the header name to authorize the API calls with URL {base_url}? Give me the one word header name and don't add extra text"
        response = get_langchain_response(base_url, domain_base_url, query)
        return {
            'type': authentication_type,
            "api_token": "{{config.api_token}}",
            "header": response,
        }
    elif authentication_type == 'OAuth':
        query = f"Please generate a JSON which contains the following keys with the values for OAuth authentication for the URL {base_url}: 'client_id', 'client_secret', token_refresh_endpoint, refresh_token, access_token_name, expires_in_name. Give me the complete JSON and don't add extra text"
        response = get_langchain_response(domain_base_url, query)
        response = {'type': authentication_type}.update(response)
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
    query = f"What is the method of authentication to authorize the API calls with this API? Following are the options: {authenticator_options}. Return the response from given options, just return the one word option. Return 'None' if don't find any"
    langchain_response = get_langchain_response(domain_base_url, query)
    authentication_type = find_best_response(
        langchain_response, authenticator_options)
    response = predict_sub_authenticator_block(
        base_url, domain_base_url, authentication_type)

    return response


def predict_requester_block(connector):
    base_url = predict_base_url(connector['base_url'], connector['sphere_endpoints'])
    requester_block = {
        "type": "HttpRequester",
        "url_base": base_url.strip(),
        "http_method": "GET",
        "authenticator": predict_authenticator_block(base_url, connector['base_url']),
    }
    return requester_block


def normalize_airbyte_requester_block(json_obj):
    def traverse(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == 'api_token':
                    obj[k] = "{{config.api_token}}"
                elif k == 'username':
                    obj[k] = "{{config.username}}"
                elif k == 'password':
                    obj[k] = "{{config.password}}"
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

    for connector in connectors:
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
        logger.info("Processed connector: {}".format(connector['name']))

    overall_similarity = (total_matches/total_airbyte_block_pair_count) * \
        100 if total_airbyte_block_pair_count != 0 else total_matches

    if not os.path.exists('data'):
        os.makedirs('data')
    with open('data/requesters_comparison.json', 'w') as f:
        json.dump({"overall_similarity": round(overall_similarity, 2),
                  "requesters": requesters_comparison}, f, indent=4)


if __name__ == "__main__":
    main('data/airbyte_lowcode_connectors.json', local=True)
