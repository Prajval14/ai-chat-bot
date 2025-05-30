# functions/config_utils.py

import os
import json
from azure.storage.blob import BlobServiceClient

BLOB_CONFIG_NAME = "bot_config.json"

DEFAULT_CONFIG = {
    "bot_name": "Smartie",
    "bot_icon": "",
    "bot_color": "#306D51"
}

def get_container_client():
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    return blob_service_client.get_container_client(AZURE_BLOB_CONTAINER)

def get_blob_config():
    try:
        container_client = get_container_client()
        blob_client = container_client.get_blob_client(BLOB_CONFIG_NAME)
        data = blob_client.download_blob().readall()
        return json.loads(data)
    except Exception:
        return None

def upload_blob_config(config):
    container_client = get_container_client()
    blob_client = container_client.get_blob_client(BLOB_CONFIG_NAME)
    blob_client.upload_blob(json.dumps(config), overwrite=True)

def ensure_blob_config():
    config = get_blob_config()
    if not config:
        upload_blob_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    return config