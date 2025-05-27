import os
import json
import logging
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from langchain.text_splitter import RecursiveCharacterTextSplitter, CharacterTextSplitter

# === Global Logging Configuration ===
LOG_FILENAME = "backend_chatbot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILENAME, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === Load Environment Variables ===
load_dotenv()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")

blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

def download_blob(blob_name, download_path):
    try:
        blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
        with open(download_path, "wb") as file:
            file.write(blob_client.download_blob().readall())
        logger.info(f"Downloaded blob '{blob_name}' to '{download_path}'")
    except Exception as e:
        logger.error(f"Failed to download blob '{blob_name}': {e}")
        raise

def upload_blob(blob_name, upload_path):
    try:
        blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
        with open(upload_path, "rb") as file:
            blob_client.upload_blob(file, overwrite=True)
        logger.info(f"Uploaded '{upload_path}' to blob '{blob_name}'")
    except Exception as e:
        logger.error(f"Failed to upload blob '{blob_name}': {e}")
        raise

def combine_files_and_chunk(
    product_blob='nestle_products.txt',
    recipe_blob='nestle_recipes.txt',
    combined_blob='combined_nestle.txt',
    chunk_blob='chunked_nestle.json',
    chunk_size=1000,
    chunk_overlap=100,
    splitter_type='recursive'
):
    try:
        logger.info("Starting file combination and chunking process.")

        # Step 1: Download both files to temp
        os.makedirs("temp", exist_ok=True)
        prod_path = "temp/products.txt"
        rec_path = "temp/recipes.txt"
        combined_path = "temp/combined.txt"
        chunk_path = "temp/chunks.json"

        download_blob(product_blob, prod_path)
        download_blob(recipe_blob, rec_path)

        # Step 2: Combine
        with open(prod_path, "r", encoding="utf-8") as f1, open(rec_path, "r", encoding="utf-8") as f2:
            combined = f1.read() + "\n" + f2.read()
        with open(combined_path, "w", encoding="utf-8") as f:
            f.write(combined)
        logger.info(f"Combined '{product_blob}' and '{recipe_blob}' into '{combined_path}'")

        # Upload combined file to blob storage
        # upload_blob(combined_blob, combined_path)

        # Step 3: Chunk the text
        if splitter_type == 'recursive':
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        else:
            text_splitter = CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        chunks = text_splitter.create_documents([combined])
        chunk_dicts = [
            {
                "chunk_id": i,
                "content": doc.page_content.replace("\n", " "),
                "metadata": doc.metadata
            } for i, doc in enumerate(chunks)
        ]

        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(chunk_dicts, f, ensure_ascii=False, indent=2)
        logger.info(f"Chunked combined text and saved to '{chunk_path}'")

        # Step 4: Upload the chunks file to blob
        upload_blob(chunk_blob, chunk_path)

        logger.info(f"Process complete: chunks uploaded as '{chunk_blob}' in Azure Blob Storage.")
        return chunk_dicts

    except Exception as e:
        logger.error(f"An error occurred in combine_files_and_chunk: {e}", exc_info=True)
        raise

# === Example Usage ===
if __name__ == "__main__":
    combine_files_and_chunk(
        product_blob='nestle_products.txt',
        recipe_blob='nestle_recipes.txt',
        combined_blob='combined_nestle.txt',
        chunk_blob='chunked_nestle.json',
        chunk_size=1000,
        chunk_overlap=100,
        splitter_type='recursive',  # or 'character'
    )