import io
import yaml
from services.generators.connector_files_generator import slugify
from services.generators.requestor import predict_requester_block
from services.generators.retriever import extract_sphere_retriever_block
from services.helpers.s3 import read_object, upload_object


def generate_manifest(connector):
    folder_name = f"source-{slugify(connector['name'])}"
    sphere_endpoints = read_object(f"{folder_name}/endpoints.txt").split('\n')
    connector['sphere_endpoints'] = sphere_endpoints
    requestor_block = predict_requester_block(connector)
    retriever_block = extract_sphere_retriever_block(connector)
    manifest_object = {
        'version': '0.2',
        'definitions': {
            'requester': requestor_block,
            'retriever': retriever_block
        }
    }
    manifest_content = yaml.dump(manifest_object)

    upload_object(io.BytesIO(manifest_content.encode(
        'utf-8')), f"{folder_name}/manifest.yaml", {'CacheControl': 'no-store'})
