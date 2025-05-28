# graph_rag.py

import os
import json
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Neo4jVector
from langchain_community.graphs import Neo4jGraph
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain.prompts import PromptTemplate

# === Globals for index and QA chain ===
VECTOR_INDEX = None
GRAPH_QA = None
GRAPH = None

# === Load env only once (for CLI or direct run) ===
load_dotenv()

# === Azure Blob Loader ===
def download_blob_to_string(blob_name):
    """Downloads a blob from Azure Blob Storage and returns its content as a string."""
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
    blob_data = blob_client.download_blob().readall()
    return blob_data.decode("utf-8")

def load_chunked_documents_from_blob(blob_name):
    """Loads chunked documents from an Azure blob and returns a list of LangChain Documents."""
    json_str = download_blob_to_string(blob_name)
    chunks = json.loads(json_str)
    docs = [
        Document(
            page_content=chunk['content'],
            metadata={
                'chunk_id': chunk['chunk_id'],
                'type': chunk.get('type', ''),
                'title': chunk.get('title', ''),
                'url': chunk.get('url', '')
            }
        ) for chunk in chunks
    ]
    return docs

# === Indexing Function ===
def graphrag_index_from_blob(
    blob_name=None,
    allowed_nodes=None,
    allowed_relationships=None
):
    """
    Ingest pre-chunked documents from Azure Blob, create entities/relationships, and build Neo4j vector index.
    """
    global VECTOR_INDEX, GRAPH_QA, GRAPH

    # === Load credentials ===
    openai_api_key = os.getenv("OPENAI_API_KEY")
    neo4j_url = os.getenv("NEO4J_URI")
    neo4j_username = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    if not all([openai_api_key, neo4j_url, neo4j_username, neo4j_password]):
        raise ValueError("Missing one or more required environment variables for OpenAI or Neo4j.")

    # === Init OpenAI and Neo4j connectors ===
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=openai_api_key)

    GRAPH = Neo4jGraph(
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password
    )

    # === Load chunked docs from Azure Blob ===
    if not blob_name:
        blob_name = os.getenv("CHUNKED_JSON_BLOB", "chunked_nestle.json")
    lc_docs = load_chunked_documents_from_blob(blob_name)

    # === (Optional) Clear existing graph ===
    GRAPH.query("MATCH (n) DETACH DELETE n;")

    allowed_nodes = ["Recipe", "Product", "Ingredient"]
    allowed_relationships = ["USES", "CONTAINS"]

    # === Transform and ingest as graph (optionally restrict schema) ===
    transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=allowed_nodes,  # List or None
        allowed_relationships=allowed_relationships,  # List or None
        node_properties=True,
        relationship_properties=True
    )
    graph_documents = transformer.convert_to_graph_documents(lc_docs)
    GRAPH.add_graph_documents(graph_documents, include_source=True)

    # === Create vector index on Neo4j graph ===
    # Note: Default "Entity" node label; update if using custom allowed_nodes
    node_label = "Entity"
    if allowed_nodes and len(allowed_nodes) == 1:
        node_label = allowed_nodes[0]

    VECTOR_INDEX = Neo4jVector.from_existing_graph(
        embedding=embeddings,
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password,
        database="neo4j",
        node_label=node_label,
        text_node_properties=["id", "text"],
        embedding_node_property="embedding",
        index_name="vector_index",
        keyword_index_name="entity_index",
        search_type="hybrid"
    )

    # Retrieve the graph schema
    schema = GRAPH.get_schema

    # === Setup Cypher QA chain ===
    template = """
    Task: Generate a Cypher statement to query the graph database.

    Instructions:
    - Recipes are labeled 'Recipe', with properties like 'id', 'description', 'cookTime'.
    - Ingredients are labeled 'Ingredient' and have a property called 'id' (e.g. id: "Olive Oil").
    - Recipes are connected to ingredients by the 'CONTAINS' relationship.
    - To find recipes that use an ingredient, match on (r:Recipe)-[:CONTAINS]->(i:Ingredient) where i.id contains or equals the ingredient name.
    - Only use labels: Recipe, Ingredient.
    - Only use relationship: CONTAINS.
    - Use the exact property names as above.

    schema:
    {schema}

    Note: Do not include explanations or apologies in your answers.
    Only return the Cypher statement.

    Question: {question}
    """

    question_prompt = PromptTemplate(
        template=template,
        input_variables=["schema", "question"]
    )

    GRAPH_QA = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=GRAPH,
        cypher_prompt=question_prompt,
        verbose=True,
        allow_dangerous_requests=True
    )

    return True  # For confirmation in logs/scripts

# === Query Functions ===
def query_vector_rag(user_query, top_k=3):    
    """
    Runs a vector search on the Neo4j vector index with the user_query and returns the top results.
    """
    global VECTOR_INDEX
    if VECTOR_INDEX is None:
        raise ValueError("Vector index not initialized. Run graphrag_index_from_blob() first.")
    results = VECTOR_INDEX.similarity_search(user_query, k=top_k)
    return results

def query_graph_qa(user_question):
    """
    Runs a Cypher-based graph QA query using the LLM Cypher chain.
    """
    GRAPH_QA = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=GRAPH,
        cypher_prompt=question_prompt,
        verbose=True,
        allow_dangerous_requests=True
    )
    if GRAPH_QA is None:
        raise ValueError("Graph QA not initialized. Run graphrag_index_from_blob() first.")
    answer = GRAPH_QA.run(user_question)
    return answer

# === For CLI/testing: Index and Query ===
if __name__ == "__main__":
    blob_name = os.getenv("CHUNKED_JSON_BLOB", "chunked_nestle.json")
    print("Indexing data from blob:", blob_name)
    graphrag_index_from_blob(blob_name)
    print("Indexing complete.\n")

    # Example vector search
    print("Sample Vector Search Results:")
    res = query_vector_rag("Which recipes use BOOST Diabetic - Strawberry?")
    for r in res:
        print("Chunk:", r.metadata.get("chunk_id"), "| Title:", r.metadata.get("title"))
        print("Content:", r.page_content[:400], "...\n")

    # Example graph QA
    print("Sample Graph Cypher QA Answer:")
    answer = query_graph_qa("Show all recipes that contain pasta.")
    print(answer)