import os
import json
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")

blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

def download_blob(blob_name, download_path):
    blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
    with open(download_path, "wb") as file:
        file.write(blob_client.download_blob().readall())

def upload_blob(blob_name, upload_path):
    blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
    with open(upload_path, "rb") as file:
        blob_client.upload_blob(file, overwrite=True)

def extract_title(content):
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("Title:"):
            return line.replace("Title:", "").strip()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("URL:"):
            url = line.replace("URL:", "").strip()
            if url.startswith("http"):
                slug = url.rstrip("/").split("/")[-1]
                slug = slug.split("?")[0].split("#")[0]
                slug = slug.split(".")[0]
                return slug.replace("-", " ").replace("_", " ").title()
            else:
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
            if len(chunk_text) < 20:
                continue
            chunk = {
                "chunk_id": i,
                "content": chunk_text,
                "type": type_,
            }
            if type_ == "recipe":
                chunk["title"] = extract_title(chunk_text)
                chunk["url"] = extract_url(chunk_text)
                if not chunk["title"]:
                    continue
            if type_ == "product":
                chunk["title"] = extract_title(chunk_text)
                chunk["url"] = extract_url(chunk_text)
                if not chunk["url"]:
                    continue
            chunks.append(chunk)
    return chunks

def process_and_chunk_files(
    product_blob='nestle_products.txt',
    recipe_blob='nestle_recipes.txt',
    chunk_blob='chunked_nestle.json'
):
    try:
        os.makedirs("temp", exist_ok=True)
        prod_path = "temp/products.txt"
        rec_path = "temp/recipes.txt"
        download_blob(product_blob, prod_path)
        download_blob(recipe_blob, rec_path)

        product_chunks = split_entries(prod_path, entry_start="URL:", type_="product")
        recipe_chunks = split_entries(rec_path, entry_start="Title:", type_="recipe")

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

        chunk_path = "temp/chunks.json"
        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)

        upload_blob(chunk_blob, chunk_path)
        return all_chunks

    except Exception as e:
        raise

if __name__ == "__main__":
    process_and_chunk_files(
        product_blob='nestle_products.txt',
        recipe_blob='nestle_recipes.txt',
        chunk_blob='chunked_nestle.json'
    )