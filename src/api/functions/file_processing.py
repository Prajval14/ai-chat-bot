# ==== Standard Library Imports ====
import os
import json

# ==== Third-Party Imports ====
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# ==== Logging Utilities ====
from functions.log_utils import get_blob_logger
logger = get_blob_logger(__name__)

# ==== Load Environment Variables ====
load_dotenv()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")

# ==== Azure Blob Client Initialization ====
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

# ==== Blob Storage Helper Functions ====
def download_blob(blob_name, download_path):
    logger.info(f"Downloading blob '{blob_name}' to local path '{download_path}'.")
    try:
        blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
        with open(download_path, "wb") as file:
            file.write(blob_client.download_blob().readall())
        logger.info(f"Downloaded blob '{blob_name}' successfully.")
    except Exception as e:
        logger.error(f"Failed to download blob '{blob_name}': {e}")
        raise

def upload_blob(blob_name, upload_path):
    logger.info(f"Uploading file '{upload_path}' to blob '{blob_name}'.")
    try:
        blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
        with open(upload_path, "rb") as file:
            blob_client.upload_blob(file, overwrite=True)
        logger.info(f"Uploaded file '{upload_path}' to blob '{blob_name}' successfully.")
    except Exception as e:
        logger.error(f"Failed to upload file '{upload_path}' to blob '{blob_name}': {e}")
        raise

# ==== Chunking & Processing Helper Functions ====
def split_by_marker(text, marker, type_):
    """Splits a text by a marker, returns a list of dicts with 'content' and 'type'."""
    parts = text.split(marker)
    chunks = []
    for i, part in enumerate(parts):
        part = part.strip()
        if part:
            if not part.startswith(marker):
                part = marker + part
            chunks.append({
                "chunk_id": i,
                "type": type_,
                "content": part
            })
    return chunks

def process_and_chunk_files(
    product_blob='nestle_products.txt',
    recipe_blob='nestle_recipes.txt',
    chunk_blob='chunked_data.json'
):
    logger.info("Starting process_and_chunk_files (minimal processing)...")
    try:
        os.makedirs("temp", exist_ok=True)
        prod_path = "temp/products.txt"
        rec_path = "temp/recipes.txt"

        logger.info("Downloading blobs...")
        download_blob(product_blob, prod_path)
        download_blob(recipe_blob, rec_path)

        # Read and split product and recipe blocks
        logger.info("Splitting product entries by 'Product:'...")
        with open(prod_path, "r", encoding="utf-8") as f:
            products_text = f.read()
        product_chunks = split_by_marker(products_text, "Product:", "product")

        logger.info("Splitting recipe entries by 'Title:'...")
        with open(rec_path, "r", encoding="utf-8") as f:
            recipes_text = f.read()
        recipe_chunks = split_by_marker(recipes_text, "Title:", "recipe")

        # Combine and re-assign unique chunk IDs
        all_chunks = []
        chunk_id = 0
        for chunk in recipe_chunks + product_chunks:
            chunk['chunk_id'] = chunk_id
            all_chunks.append(chunk)
            chunk_id += 1

        chunk_path = "temp/chunks_combined.json"
        logger.info(f"Writing {len(all_chunks)} chunks to local file '{chunk_path}'.")
        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)

        logger.info(f"Uploading chunked file to blob '{chunk_blob}'.")
        upload_blob(chunk_blob, chunk_path)

        logger.info("process_and_chunk_files (minimal) completed successfully.")
        return all_chunks

    except Exception as e:
        logger.error(f"Error in process_and_chunk_files: {e}", exc_info=True)
        raise

# ==== Entrypoint Functions ====
def main():
    return process_and_chunk_files()

if __name__ == "__main__":
    process_and_chunk_files()