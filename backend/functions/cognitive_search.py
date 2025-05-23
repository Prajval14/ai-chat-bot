# import required packages
from dotenv import load_dotenv
load_dotenv()
import openai
import os
import json
import uuid
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import Vector
from azure.search.documents.indexes.models import (
    ComplexField,
    CorsOptions,
    SearchIndex,
    ScoringProfile,
    SearchFieldDataType,
    SimpleField,
    SearchField,
    SearchableField,
    VectorSearch,
    HnswVectorSearchAlgorithmConfiguration
)

# Set your OpenAI API key
openai.api_key = os.environ["OPENAI_API_KEY"]  # or set directly: openai.api_key = "your-key"

# Create vector configuration
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

# Create a search index client
AZURE_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]  # or set directly
AZURE_SEARCH_KEY = os.environ["AZURE_SEARCH_KEY"]            # or set directly
client = SearchIndexClient(AZURE_SEARCH_ENDPOINT, AzureKeyCredential(AZURE_SEARCH_KEY))

# Create the index
index_name = "nestledata"
fields = [
        SimpleField(name="documentId", type=SearchFieldDataType.String, filterable=True, sortable=True, key=True),     
        SearchableField(name="content", type=SearchFieldDataType.String),        
        SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), searchable=True, vector_search_dimensions = 1536, vector_search_configuration ="my-vector-config", vector_search_profile_name="my-vector-profile")
    ]

index = SearchIndex(
    name=index_name,
    fields=fields,
    vector_search=vector_search
)

result = client.create_index(index)

# Chunking the text
loader = TextLoader("../docs/nestle_sample_data.txt", encoding="utf-8")
documents = loader.load()
text_splitter = CharacterTextSplitter(chunk_size=1200, chunk_overlap=50)
documents = text_splitter.split_documents(documents)

print(documents)

# Define your embedding function
def generate_embeddings(text):
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response["data"][0]["embedding"]

# Construct json
docs = []
for doc in documents:
    docs.append({
        "documentId": str(uuid.uuid4()),
        "content": doc.page_content,
        "embedding": generate_embeddings(doc.page_content)
    })
json_data = json.dumps(docs)

with open("NestleContent.json", "w") as f:
    f.write(json_data)

# Upload docs to index
with open('NestleContent.json', 'r') as f:
    documents = json.load(f)

search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=index_name, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
result = search_client.upload_documents(documents)

# test query
query = "How many total brands does nestle have?"
vector = Vector(value=generate_embeddings(query), k=2, fields="embedding")

results = search_client.search(
    search_text=None,
    vectors=[vector],
    select=["content"]
)

input_text = " "
for result in results:
    input_text += result['content'] + " "

# Calling OpenAI endpoint
response = openai.ChatCompletion.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer questions."},
        {"role": "user", "content": f"Context: {input_text}\n\nQuestion: {query}"}
    ],
    max_tokens=100,
    temperature=0
)

print(response['choices'][0]['message']['content'])