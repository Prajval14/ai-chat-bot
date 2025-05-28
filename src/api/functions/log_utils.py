import os
import logging
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()

class BlobStorageLogHandler(logging.Handler):
    def __init__(self, connection_string, container_name, blob_name):
        super().__init__()
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
    def emit(self, record):
        log_entry = self.format(record) + "\n"
        try:
            existing = self.blob_client.download_blob().readall().decode('utf-8')
        except:
            existing = ""
        new_content = existing + log_entry
        self.blob_client.upload_blob(new_content, overwrite=True)

def get_blob_logger(name="myapp", level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Avoid duplicate handlers if already set
    if not logger.handlers:
        # Load these from env or config in production
        CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")
        BLOB = "logs/mylog.txt"
        blob_handler = BlobStorageLogHandler(CONNECTION_STRING, CONTAINER, BLOB)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        blob_handler.setFormatter(formatter)
        logger.addHandler(blob_handler)
    return logger