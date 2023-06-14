import io
import json
from services.helpers.s3 import read_object, upload_object


def generate_connectors(read_filename, write_filename):
    production_connectors = []
    file_content = read_object(read_filename)
    connectors = json.loads(file_content)
    for connector in connectors:
        production_connector = {
            'name': connector['name'],
            'base_url': connector['base_url'],
            'start_url': connector['start_url'],
        }
        production_connectors.append(production_connector)

    production_connectors = json.dumps(production_connectors, indent=4)
    file_obj = io.BytesIO(production_connectors.encode('utf-8'))
    upload_object(file_obj, write_filename, extraArgs={'CacheControl': 'no-store'})


if __name__ == "__main__":
    generate_connectors('airbyte_lowcode_connectors.json', 'production_connectors.json')
