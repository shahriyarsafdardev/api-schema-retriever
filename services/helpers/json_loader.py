import json
import io
from services.helpers.logger import getLogger
from services.helpers.s3 import read_object, upload_object

logger = getLogger()


def load_json(filename, local=False):
    if local:
        # Reading file from local storage
        with open(filename, 'r') as f:
            connectors = json.load(f)
    else:
        # Reading file from S3
        file_content = read_object(filename)
        connectors = json.loads(file_content)
    
    return connectors

def save_json(filename, connectors, local=False):
    if local:
        # Saving file to local storage
        with open(filename, 'w') as f:
            json.dump(connectors, f, indent=4)
    else:
        # Saving file to S3
        updated_connectors = json.dumps(connectors, indent=4)
        file_obj = io.BytesIO(updated_connectors.encode('utf-8'))
        upload_object(file_obj, filename, extraArgs={'CacheControl': 'no-store'})
        