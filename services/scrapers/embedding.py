import json
from logging import getLogger
from pipes import quote
from services.helpers.pinecone_db import store_chunks
from services.scrapers.embedding_helper import split_into_chunks, text_slice_to_vector
from services.helpers.s3 import read_object


logger = getLogger()
AIRBYTE_CONNECTORS_FILE = 'airbyte_connectors.json'
PRODUCTION_CONNECTORS_FILE = 'production_connectors.json'


def embedding(connector_name):
    file_content = read_object(AIRBYTE_CONNECTORS_FILE)
    connectors = json.loads(file_content)

    for connector in connectors:
        if connector['name'] != connector_name:
            continue

        quoted_base_url = quote(connector['base_url'], safe="")
        concise_bulk_file = read_object(quoted_base_url + '-bulk-concise' + '.md')

        # generating chunks and storing to pinecone
        chunks = split_into_chunks(concise_bulk_file)
        logger.info('Generated {} chunks for {}'.format(len(chunks), connector["name"]))
        chunks = [text_slice_to_vector(chunk, connector['base_url']) for chunk in chunks]
        logger.info('Generated embeddings for {}'.format(connector["name"]))
        store_chunks(chunks)
        logger.info('Generated vectors for {}'.format(connector["name"]))
        break