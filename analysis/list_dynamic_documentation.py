import json
import requests
from bs4 import BeautifulSoup
from services.helpers.s3 import read_object


def download_html(page_url, verbose=False):
    """
    This function downloads the HTML content from a given URL.

    :param page_url: String containing the URL from which the HTML content is to be downloaded.
    :param verbose: Boolean indicating whether to print debug information.
    :return: List of 'a' tags (links) found in the HTML content of the webpage.
    """
    try:
        response = requests.get(page_url, timeout=20)
        response.raise_for_status()
        
        # Parse the response text using BeautifulSoup with html.parser
        soup = BeautifulSoup(response.text, 'html.parser')
        a_tags_list = soup.find_all('a', href=True)

        if verbose:
            print(f"Downloaded HTML from: {page_url}")
            print(f"Found {len(a_tags_list)} link(s): {[tag['href'] for tag in a_tags_list]}")

        return a_tags_list
    except Exception as e:
        if verbose:
            print(f"Error downloading: {page_url}")
        return None


def list_dynamic_documentation(filename, local=False, verbose=False):
    """
    This function reads the JSON file with connector configurations and lists those that have dynamic documentation.

    :param filename: String containing the path to the JSON file.
    :param verbose: Boolean indicating whether to print debug information.
    :return: List of connector names with dynamic documentation.
    """
    dynamic_docs = []

    if local:
        # Reading file from local storage
        with open(filename, 'r') as f:
            connectors = json.load(f)
    else:
        # Reading file from S3
        file_content = read_object(filename)
        connectors = json.loads(file_content)

    for connector in connectors:
        name = connector['name']
        start_url = connector['start_url']
        base_url = connector['base_url']

        if verbose:
            print(f'Connector: {name}, Start URL: {start_url}, Base URL: {base_url}')

        a_tags_list = download_html(start_url, verbose=verbose)

        # Check if the page is dynamic
        if not a_tags_list:
            dynamic_docs.append(connector)

    # Log the names of connectors with dynamic documentation
    print(f'Connectors with dynamic documentation: {len(dynamic_docs)}')

    # Save dynamic_docs to a JSON file
    with open('data/dynamic_connectors.json', 'w') as f:
        json.dump(dynamic_docs, f, indent=4)

# Usage:
list_dynamic_documentation('airbyte_connectors.json', local=False, verbose=True)
