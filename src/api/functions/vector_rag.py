import os
import json
import uuid
from dotenv import load_dotenv

from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import Vector
from azure.search.documents.indexes.models import (
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    SearchIndex,
    HnswVectorSearchAlgorithmConfiguration
)
from openai import OpenAI

# ---- Centralized logger ----
from functions.log_utils import get_blob_logger
logger = get_blob_logger(__name__)

load_dotenv()
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")
CHUNKED_JSON_BLOB = os.getenv("CHUNKED_JSON_BLOB", "chunked_nestle.json")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def download_blob_to_string(blob_name):
    logger.info(f"Downloading blob '{blob_name}' from Azure Blob Storage...")
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
        blob_data = blob_client.download_blob().readall()
        logger.info(f"Blob '{blob_name}' downloaded successfully.")
        return blob_data.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to download blob '{blob_name}': {e}")
        raise

def create_vector_index():
    index_name = "nestledata"
    logger.info(f"Creating Azure Cognitive Search vector index: '{index_name}'")
    fields = [
        SimpleField(name="documentId", type=SearchFieldDataType.String, filterable=True, sortable=True, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="type", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_id", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="url", type=SearchFieldDataType.String),
        SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), searchable=True,
                    vector_search_dimensions=1536, vector_search_configuration="my-vector-config", vector_search_profile_name="my-vector-profile")
    ]
    vector_search = VectorSearch(
        algorithm_configurations=[
            HnswVectorSearchAlgorithmConfiguration(
                name="my-vector-config",
                kind="hnsw",
                parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine"
                }
            )
        ]
    )
    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search
    )
    client = SearchIndexClient(AZURE_SEARCH_ENDPOINT, AzureKeyCredential(AZURE_SEARCH_KEY))
    try:
        result = client.create_index(index)
        logger.info(f"Vector index '{index_name}' created successfully.")
    except Exception as e:
        logger.warning(f"Index '{index_name}' may already exist or creation failed: {e}")
    return index_name

def generate_embeddings(text):
    logger.info("Generating OpenAI embeddings for text chunk.")
    try:
        response = openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        embedding = response.data[0].embedding
        logger.info("Embedding generated successfully.")
        return embedding
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise

def ingest_docs_to_index(chunked_blob_name, index_name):
    logger.info(f"Ingesting documents from '{chunked_blob_name}' into Azure Search index '{index_name}'")
    try:
        chunked_json_str = download_blob_to_string(chunked_blob_name)
        docs_data = json.loads(chunked_json_str)
        docs = []
        for i, doc in enumerate(docs_data):
            try:
                docs.append({
                        "documentId": str(uuid.uuid4()),
                        "content": doc["content"],
                        "embedding": generate_embeddings(doc["content"]),
                        "type": doc.get("type", "unknown"),
                        "chunk_id": doc.get("chunk_id", -1),
                        "title": doc.get("title", ""),
                        "url": doc.get("url", "")
                })
                logger.info(f"Document {i+1}/{len(docs_data)} embedded and prepared.")
            except Exception as e:
                logger.error(f"Failed to process document {i+1}: {e}")
        search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=index_name, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
        try:
            result = search_client.upload_documents(docs)
            logger.info(f"Uploaded {len(docs)} documents to index '{index_name}'.")
        except Exception as e:
            logger.error(f"Failed to upload documents to index '{index_name}': {e}")
    except Exception as e:
        logger.error(f"Error during document ingestion: {e}")
        raise

def query_vector_rag(query, index_name):
    logger.info(f"Running vector search for query: '{query}'")
    try:
        search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=index_name, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
        query_embedding = generate_embeddings(query)
        vector = Vector(value=query_embedding, k=5, fields="embedding")
        results = search_client.search(
            search_text=None,
            vectors=[vector],
            select=["content"]
        )
        input_text = ""
        count = 0
        for result in results:
            if result.get('type') == 'recipe':
                input_text += "\n\n---\n\n" + result['content']
                count += 1
        logger.info(f"Vector search returned {count} relevant recipes.")
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are a helpful recipe assistant. "
                    "The context contains one or more recipes and product descriptions. "
                    "If the user asks for a recipe, find the most relevant recipe from the context and respond with the recipe title, a short summary, and the ingredients list. "
                    "If no recipe is found, say: The answer is not in the context provided."
                )},
                {"role": "user", "content": f"Context: {input_text}\n\nQuestion: {query}"}
            ],
            max_tokens=200,
            temperature=0
        )
        answer = response.choices[0].message.content
        logger.info("Received answer from OpenAI completion endpoint.")
        return answer
    except Exception as e:
        logger.error(f"Error during vector RAG query: {e}", exc_info=True)
        raise

def main():
    index_name = create_vector_index()
    ingest_docs_to_index(CHUNKED_JSON_BLOB, index_name)

if __name__ == "__main__":
    try:
        index_name = create_vector_index()
        ingest_docs_to_index(CHUNKED_JSON_BLOB, index_name)
        logger.info("Vector index creation and document ingestion completed.")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise