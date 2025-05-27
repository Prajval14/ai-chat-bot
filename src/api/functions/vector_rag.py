import os
import json
import uuid
import logging
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

# === Global Logging ===
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

# === Load ENV ===
load_dotenv()
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")
CHUNKED_JSON_BLOB = os.getenv("CHUNKED_JSON_BLOB", "chunked_nestle.json")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def download_blob_to_string(blob_name):
    logger.info(f"Attempting to download blob: {blob_name}")
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
    blob_data = blob_client.download_blob().readall()
    logger.info(f"Downloaded blob: {blob_name}")
    return blob_data.decode("utf-8")

# --- INDEXING PHASE ---
def create_vector_index():
    logger.info("Starting vector index creation.")    
    index_name = "nestledata"
    fields = [
        SimpleField(name="documentId", type=SearchFieldDataType.String, filterable=True, sortable=True, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
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
        logger.info(f"Created Azure Cognitive Search vector index: {index_name}")
    except Exception as e:
        logger.error(f"Could not create index (might exist): {e}")
    return index_name

def generate_embeddings(text):
    logger.info("Generating embeddings for chunk...")
    response = openai_client.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    embedding = response["data"][0]["embedding"]
    logger.info("Embeddings generated.")
    return embedding

def ingest_docs_to_index(chunked_blob_name, index_name):
    logger.info("Starting document ingestion to index.")
    chunked_json_str = download_blob_to_string(chunked_blob_name)
    docs_data = json.loads(chunked_json_str)

    docs = []
    for doc in docs_data:
        try:
            docs.append({
                "documentId": str(uuid.uuid4()),
                "content": doc["content"],
                "embedding": generate_embeddings(doc["content"])
            })
        except Exception as e:
            logger.error(f"Embedding failed for a chunk: {e}")

    logger.info(f"Prepared {len(docs)} documents for upload to Azure Cognitive Search.")

    # Upload docs
    search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=index_name, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
    try:
        result = search_client.upload_documents(docs)
        logger.info("Documents uploaded to vector index.")
    except Exception as e:
        logger.error(f"Failed to upload documents: {e}")

# --- QUERY PHASE ---
def query_vector_rag(query, index_name):
    logger.info(f"Starting RAG query for: {query}")
    search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=index_name, credential=AzureKeyCredential(AZURE_SEARCH_KEY))

    # Step 1: Create embedding for query
    query_embedding = generate_embeddings(query)

    # Step 2: Search similar vectors
    vector = Vector(value=query_embedding, k=5, fields="embedding")
    results = search_client.search(
        search_text=None,
        vectors=[vector],
        select=["content"]
    )
    input_text = ""
    for result in results:
        input_text += result['content'] + " "
    print(f"Retrieved context:\n{input_text}\n")
    logger.info("Context chunks retrieved for query.")

    # Step 3: Call LLM
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Use ONLY the provided context to answer the question. If you cannot find the answer in the context, say: 'The answer is not in the context provided."},
            {"role": "user", "content": f"Context: {input_text}\n\nQuestion: {query}"}
        ],
        max_tokens=200,
        temperature=0
    )
    answer = response['choices'][0]['message']['content']
    logger.info(f"LLM response generated: {answer}")
    return answer

# === MAIN ===
if __name__ == "__main__":
    logger.info("Starting RAG indexing and querying workflow.")

    index_name = create_vector_index()
    ingest_docs_to_index(CHUNKED_JSON_BLOB, index_name)

    # Example query
    user_query = "How many total brands does nestle have?"
    answer = query_vector_rag(user_query, index_name)
    print("Answer:", answer)
    logger.info("Completed full workflow.")