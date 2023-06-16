from services.helpers.logger import getLogger
from services.helpers.json_loader import load_connectors
from urllib.parse import quote
from services.helpers.s3 import list_objects

logger = getLogger()


def success_percentage(filename, local=False):

    connectors = load_connectors(filename, local=local)
    total_connectors = len(connectors)
    more_than_one_file_count = 0

    for idx, connector in enumerate(connectors):

        base_url = connector['base_url']
        quoted_base_url = quote(base_url, safe="")
        file_keys = list_objects([quoted_base_url, ".html"])

        logger.info(f'Found {len(file_keys)} files for {connector["name"]}')

        if len(file_keys) > 1:
            more_than_one_file_count += 1

    percentage_more_than_one_file = (
        more_than_one_file_count / total_connectors) * 100
    logger.info(
        f'Percentage of connectors with more than one file key: {percentage_more_than_one_file}%')


# Usage:
success_percentage('data/dynamic_connectors.json', local=True)
