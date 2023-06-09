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


def load_json_from_file(filename):
    with open(filename, 'r') as file:
        return json.load(file)


def load_json_from_s3(filename):
    file_content = read_object(filename)
    if file_content is None:
        return []
    return json.loads(file_content)


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


def find_best_response(response, options):
    """Return the first matching response from the options, else 'None'."""
    response = response.lower()
    return next((option for option in options if option.lower() in response), 'None')


def get_langchain_response(domain_base_url, query):
    logger.info('Query: {}'.format(query))
    docsearch = Pinecone.from_existing_index(
        settings.pinecone_index_name, embeddings)
    docs = docsearch.similarity_search(
        query, k=5, filter={'domain_base_url': domain_base_url})
    response = chain.run(input_documents=docs, question=query)
    logger.info('Response: {}'.format(response))
    return response


def predict_sub_authenticator_block(base_url, domain_base_url, authentication_type):
    if authentication_type == "BasicHttpAuthenticator":
        return {
            "type": "BasicHttpAuthenticator",
            "username": "{{config.username}}",
        }
    elif authentication_type == "BearerAuthenticator":
        return {
            "type": "BearerAuthenticator",
            "api_token": "{{config.auth_token}}",
        }
    elif authentication_type == 'ApiKeyAuthenticator':
        query = f"What is the header name to authorize the API calls with URL {base_url}? Give me the one word header name and don't add extra text"
        response = get_langchain_response(base_url, domain_base_url, query)
        return {
            'type': authentication_type,
            "api_token": "{{config.api_key}}",
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
    base_url = get_base_url(domain_base_url)
    query = f"What is the method of authentication to authorize the API calls with this API? Following are the options: {authenticator_options}. Return the response from given options, just return the one word option. Return 'None' if don't find any"
    langchain_response = get_langchain_response(domain_base_url, query)
    authentication_type = find_best_response(
        langchain_response, authenticator_options)
    response = predict_sub_authenticator_block(
        base_url, domain_base_url, authentication_type)

    return response


def extract_sphere_requester_block(connector):
    base_url = get_base_url(connector['domain_base_url'])
    requester_block = {
        "type": "HttpRequester",
        "url_base": base_url,
        "http_method": "GET",
        "authenticator": predict_authenticator_block(base_url, connector['domain_base_url']),
    }
    return requester_block


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
    connector_name = connector_name.lower()

    connector_folder_name = connector_name.replace(" ", "-").replace("_", "-")
    connector_file_name = connector_folder_name.replace('-', '_')

    url = f"https://raw.githubusercontent.com/airbytehq/airbyte/master/airbyte-integrations/connectors/source-{connector_folder_name}/source_{connector_file_name}/manifest.yaml"

    response = requests.get(url)

    if response.status_code == 200:
        try:
            data = yaml.safe_load(response.text)
            auth_block = find_airbyte_requester_block(data)
            return auth_block if auth_block is not None else {}
        except Exception as e:
            return {}
    else:
        logger.error('\nFailed to fetch file for {}, status code: {}'.format(
            connector_name, response.status_code))
        return {}


def calculate_line_similarity(airbyte_block, sphere_block):
    airbyte_block_lines = set(airbyte_block.strip().split('\n'))
    sphere_block_lines = set(sphere_block.strip().split('\n'))

    matching_lines = airbyte_block_lines.intersection(sphere_block_lines)

    percentage_matching = (len(matching_lines) / airbyte_block_lines) * 100

    return percentage_matching


def main(filename, local=False):
    connectors = load_json_from_file(
        filename) if local else load_json_from_s3(filename)

    requesters_comparison = {}

    for connector in connectors:
        if connector.get('airbyte_status') != 'lowcode-connector':
            continue

        airbyte_requester_block = extract_airbyte_requester_block(
            connector['name'])
        sphere_requester_block = extract_sphere_requester_block(connector)
        requester_block_similarity = calculate_line_similarity(
            json.dumps(airbyte_requester_block), json.dumps(sphere_requester_block))

        requesters_comparison[connector['name']] = {
            'airbyte_requester_block': airbyte_requester_block,
            'sphere_requester_block': sphere_requester_block,
            'similarity': requester_block_similarity,
        }
        logger.info("Processed connector: {}".format(connector['name']))

    if not os.path.exists('exports'):
        os.makedirs('exports')
    with open('exports/requesters_comparison.json', 'w') as f:
        json.dump(requesters_comparison, f, indent=4)


if __name__ == "__main__":
    main('airbyte_connectors.json')
