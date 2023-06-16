import datetime
import time
from services.scrapers.domain_processor import read_all_connector, upload_all_connector

PRODUCTION_CONNECTORS_FILE = 'production_connectors.json'


def populate_created_at():
    production_connectors = read_all_connector(PRODUCTION_CONNECTORS_FILE)

    sorted_production_connectors = sorted(
        production_connectors, key=lambda x: x['name'], reverse=False)

    for connector in sorted_production_connectors:
        created_at = datetime.datetime.now() - datetime.timedelta(days=2)
        time.sleep(1)
        connector.update({'created_at': created_at.strftime(
            "%Y-%m-%d %H:%M:%S")})

    upload_all_connector(PRODUCTION_CONNECTORS_FILE,
                         sorted_production_connectors)


if __name__ == '__main__':
    populate_created_at()
