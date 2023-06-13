from scripts.clean_sphere_endpoints import clean_sphere_endpoints
from scripts.compare_lowcode_endpoints import compare_lowcode_endpoints
from scripts.endpoints_success_percent import get_endpoints_success_percent

if __name__ == '__main__':
    # this function replaces all query parameters with string 'param' and strips special characters
    # to reset this whole process, replace the contents of the local file in the function below with the contents of its S3 file
    clean_sphere_endpoints('data/airbyte_lowcode_connectors.json', local=True)
    
    # this function compares the endpoints and creates a new json file with the common endpoints
    compare_lowcode_endpoints('data/airbyte_lowcode_connectors.json', local=True)

    # this function analyses the file created from the above function and lists the endpoint accuracy
    get_endpoints_success_percent('data/lowcode_connectors_comparison.json', 'lowcode-connector', True)

