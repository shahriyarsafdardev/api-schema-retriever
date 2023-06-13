from urllib.parse import quote
from services.helpers.s3 import read_object
from services.helpers.logger import getLogger
from services.helpers.pinecone_db import store_chunks
import json
from services.scrapers.embedding_helper import split_into_chunks, text_slice_to_vector

logger = getLogger()


def create_embeddings(filename, local=False):
	if local:
		with open(filename, 'r') as f:
			connectors = json.load(f)
	else:
		file_content = read_object(filename)
		connectors = json.loads(file_content)

	for connector in connectors:
		# reading the concise bulk file
		if connector['airbyte_status'] != 'lowcode-connector':
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

create_embeddings('data/airbyte_lowcode_connectors.json', local=True)

