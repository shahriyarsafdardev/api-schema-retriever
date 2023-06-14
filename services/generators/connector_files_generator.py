import re
import io
import zipfile
from services.helpers.s3 import upload_object


def slugify(s):
    s = s.lower()
    s = re.sub(r'[^a-z0-9 -]', '', s)
    s = re.sub(r'\s+', '-', s)
    s = s.strip()
    return s


def create_empty_files_on_s3(connector_name):
    folder_name = f"source-{slugify(connector_name)}"
    zip_file_key = f"{folder_name}.zip"
    zip_buffer = io.BytesIO()

    upload_object(io.BytesIO(b''), f"{folder_name}/schemas/", {'CacheControl': 'no-store'})

    with zipfile.ZipFile(zip_buffer, mode='a', compression=zipfile.ZIP_DEFLATED) as archive:
        pass

    zip_buffer.seek(0)
    upload_object(zip_buffer, zip_file_key, {'CacheControl': 'no-store'})
