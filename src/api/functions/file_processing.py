import os
import json
import logging
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

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
    blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
    with open(download_path, "wb") as file:
        file.write(blob_client.download_blob().readall())
    logger.info(f"Downloaded blob '{blob_name}' to '{download_path}'")

def upload_blob(blob_name, upload_path):
    blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
    with open(upload_path, "rb") as file:
        blob_client.upload_blob(file, overwrite=True)
    logger.info(f"Uploaded '{upload_path}' to blob '{blob_name}'")

def extract_title(content):
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Title:"):
            return line.replace("Title:", "").strip()
    # Try to extract a name from URL if Title: not found
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("URL:"):
            url = line.replace("URL:", "").strip()
            if url.startswith("http"):
                slug = url.rstrip("/").split("/")[-1]
                # Remove query params/fragments if any
                slug = slug.split("?")[0].split("#")[0]
                # Remove file extensions if any
                slug = slug.split(".")[0]
                # Replace dashes/underscores with spaces and capitalize
                return slug.replace("-", " ").replace("_", " ").title()
            else:
                # If URL doesn't start with http, just use what's after 'URL:'
                return url.title()
    return ""

def extract_url(content):
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("URL:"):
            url = line.replace("URL:", "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                return url
    return ""

def split_entries(file_path, entry_start, type_):
    with open(file_path, "r", encoding="utf-8") as f:
        data = f.read()
    entries = data.split(entry_start)
    chunks = []
    for i, entry in enumerate(entries):
        entry = entry.strip()
        if entry:
            chunk_text = f"{entry_start}{entry}" if not entry.startswith(entry_start) else entry
            # Remove empty or short/garbage entries
            if len(chunk_text) < 20:
                continue
            chunk = {
                "chunk_id": i,
                "content": chunk_text,
                "type": type_,
            }
            # Extract and store title/url for easier downstream usage (optional)
            if type_ == "recipe":
                chunk["title"] = extract_title(chunk_text)
                chunk["url"] = extract_url(chunk_text)
                if not chunk["title"]:  # Skip recipe if title is missing
                    continue
            if type_ == "product":
                chunk["title"] = extract_title(chunk_text)
                chunk["url"] = extract_url(chunk_text)
                if not chunk["url"]:  # Skip product if no URL
                    continue
            chunks.append(chunk)
    return chunks

def process_and_chunk_files(
    product_blob='nestle_products.txt',
    recipe_blob='nestle_recipes.txt',
    chunk_blob='chunked_nestle.json'
):
    try:
        logger.info("Starting logical chunking process by entry.")

        # Step 1: Download files
        os.makedirs("temp", exist_ok=True)
        prod_path = "temp/products.txt"
        rec_path = "temp/recipes.txt"
        download_blob(product_blob, prod_path)
        download_blob(recipe_blob, rec_path)

        # Step 2: Split into logical chunks
        product_chunks = split_entries(prod_path, entry_start="URL:", type_="product")
        recipe_chunks = split_entries(rec_path, entry_start="Title:", type_="recipe")

        # Combine and assign unique IDs (chunk_id already unique within each, but make unique globally)
        all_chunks = []
        chunk_id = 0
        for chunk in recipe_chunks:
            chunk['chunk_id'] = chunk_id
            all_chunks.append(chunk)
            chunk_id += 1
        for chunk in product_chunks:
            chunk['chunk_id'] = chunk_id
            all_chunks.append(chunk)
            chunk_id += 1

        # Step 3: Save and upload
        chunk_path = "temp/chunks.json"
        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved logical chunks to '{chunk_path}'")

        upload_blob(chunk_blob, chunk_path)
        logger.info(f"Process complete: chunks uploaded as '{chunk_blob}' in Azure Blob Storage.")
        return all_chunks

    except Exception as e:
        logger.error(f"Error in process_and_chunk_files: {e}", exc_info=True)
        raise

# === Example Usage ===
if __name__ == "__main__":
    process_and_chunk_files(
        product_blob='nestle_products.txt',
        recipe_blob='nestle_recipes.txt',
        chunk_blob='chunked_nestle.json'
    )