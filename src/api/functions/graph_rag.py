import os
import re
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.graphs import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain

# ---- Centralized logger ----
from functions.log_utils import get_blob_logger
logger = get_blob_logger(__name__)

# === Block: Load environment and setup Azure Blob ===
load_dotenv()
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "files")
PRODUCTS_BLOB = os.getenv("NESTLE_PRODUCTS_BLOB", "nestle_products.txt")
RECIPES_BLOB = os.getenv("NESTLE_RECIPES_BLOB", "nestle_recipes.txt")
BLOB_SERVICE_CLIENT = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

# === Block: Blob file loading utility ===
def load_blob_text(blob_name):
    logger.info(f"Loading blob: {blob_name}")
    blob_client = BLOB_SERVICE_CLIENT.get_blob_client(container=AZURE_BLOB_CONTAINER, blob=blob_name)
    content = blob_client.download_blob().readall().decode("utf-8")
    return content

# === Block: Data parsing functions ===
def parse_products(raw):
    # Split at 'Product:' but keep the delimiter
    product_blocks = re.split(r"\n(?=Product: )", raw)
    products = []
    for block in product_blocks:
        if not block.strip() or not block.startswith("Product:"):
            continue
        prod = {}
        # Basic fields
        m = re.search(r"Product:\s*(.+)", block)
        if m:
            prod["name"] = m.group(1).strip()
            prod["id"] = prod["name"]
        m = re.search(r"URL:\s*(.+)", block)
        if m:
            prod["url"] = m.group(1).strip()
        m = re.search(r"Description:\s*(.+)", block)
        if m:
            prod["description"] = m.group(1).strip()
        m = re.search(r"Features and Benefits:\s*(.+)", block)
        if m:
            prod["features"] = m.group(1).strip()

        # Nutrition
        nutrition = {}
        nutrition_block = re.search(r"Nutrition Information:([^\n]*)(.+?)(?=(\n\S+:|$))", block, re.S)
        if nutrition_block:
            nut_lines = nutrition_block.group(2).strip().split("\n")
            for line in nut_lines:
                key_val = re.match(r"([A-Za-z ]+):\s*([\d\.]+)\s*([a-zA-Z%]*)", line)
                if key_val:
                    k = key_val.group(1).strip()
                    v = key_val.group(2).strip()
                    u = key_val.group(3).strip()
                    nutrition[k.lower().replace(' ', '_')] = v
                    if u:
                        nutrition[f"{k.lower().replace(' ', '_')}_unit"] = u
                # Sub-nutrients (within brackets)
                sub_match = re.search(r"\[Sub-nutrients: (.+?)\]", line)
                if sub_match:
                    for sub in sub_match.group(1).split(";"):
                        sub_kv = re.match(r"([^:]+):\s*([\d\.]+)\s*([a-zA-Z%]*)", sub.strip())
                        if sub_kv:
                            sk = sub_kv.group(1).strip()
                            sv = sub_kv.group(2).strip()
                            su = sub_kv.group(3).strip()
                            nutrition[sk.lower().replace(' ', '_')] = sv
                            if su:
                                nutrition[f"{sk.lower().replace(' ', '_')}_unit"] = su
            prod.update(nutrition)

        # Ingredients (may have trailing spaces)
        m = re.search(r"Ingredients:\s*([^\n]+)", block)
        if m:
            prod["ingredients"] = m.group(1).strip()
        products.append(prod)
    return products

def parse_recipes(raw):
    recipe_blocks = re.split(r"\n(?=Title: )", raw)
    recipes = []
    for block in recipe_blocks:
        if not block.strip() or not block.startswith("Title:"):
            continue
        rec = {}
        m = re.search(r"Title:\s*(.+)", block)
        if m:
            rec["name"] = m.group(1).strip()
            rec["id"] = rec["name"]
        m = re.search(r"URL:\s*(.+)", block)
        if m:
            rec["url"] = m.group(1).strip()
        m = re.search(r"Description:\s*(.+)", block)
        if m:
            rec["description"] = m.group(1).strip()
        m = re.search(r"Prep Time:\s*(.+)", block)
        if m:
            rec["prep_time"] = m.group(1).strip()
        m = re.search(r"Cook Time:\s*(.+)", block)
        if m:
            rec["cook_time"] = m.group(1).strip()
        m = re.search(r"Servings:\s*(.+)", block)
        if m:
            rec["servings"] = m.group(1).strip()

        # Parse ingredients as multiple "- " lines
        ingr_match = re.search(r"Ingredients:\s*((?:\n\s*-\s*.*)+)", block)
        if ingr_match:
            ingr_lines = ingr_match.group(1).split("\n")
            # Remove duplicates if present (seen in your sample data)
            ingr_set = []
            for l in ingr_lines:
                cleaned = l.lstrip(" -").strip()
                if cleaned and cleaned not in ingr_set:
                    ingr_set.append(cleaned)
            rec["ingredients"] = ingr_set

        # Instructions as numbered lines
        instr_match = re.search(r"Instructions:\s*((?:\n\s*\d+\.\s.*)+)", block)
        if instr_match:
            instr_lines = instr_match.group(1).split("\n")
            instr_set = []
            for l in instr_lines:
                cleaned = l.strip()
                if cleaned and cleaned not in instr_set:
                    instr_set.append(cleaned)
            rec["instructions"] = instr_set

        m = re.search(r"Tags:\s*(.+)", block)
        if m:
            rec["tags"] = [x.strip() for x in m.group(1).split(",")]
        m = re.search(r"Tip:\s*(.+)", block)
        if m:
            rec["tip"] = m.group(1).strip()
        recipes.append(rec)
    return recipes

# === Block: Neo4j loader utilities ===
def flatten_props(props):
    flat = {}
    for k, v in props.items():
        if isinstance(v, list):
            flat[k] = "; ".join(str(x) for x in v)
        else:
            flat[k] = v
    return flat

def add_products_and_recipes_to_neo4j(graph, products, recipes):
    for prod in products:
        prod = {k: v for k, v in prod.items() if not isinstance(v, dict)}
        prod = flatten_props(prod)
        graph.query(
            """
            MERGE (p:Product {id: $id})
            SET p += $props
            """,
            params={"id": prod["id"], "props": prod}
        )
    for rec in recipes:
        rec = {k: v for k, v in rec.items() if not isinstance(v, dict)}
        rec = flatten_props(rec)
        graph.query(
            """
            MERGE (r:Recipe {id: $id})
            SET r += $props
            """,
            params={"id": rec["id"], "props": rec}
        )

# === Block: Cypher QA prompt ===
cypher_prompt = PromptTemplate(
    template="""
    Task: Generate a Cypher statement to query the graph database.
    Instructions:
    - Use only the exact node labels, relationship types, and property names as found in the schema below.
    - If no relationship exists between two node types, use only their properties for filtering or matching.
    - Do not invent or assume relationships that are not explicitly shown in the schema.
    - For product/recipe suggestion questions (e.g., gifts, recommendations, healthy options), retrieve a list of relevant products or recipes, including their names, descriptions, and if available, image URLs and purchase/reference links.
    - For questions about nutrition, ingredients, features, or other factual properties, retrieve the specific values and units for the requested product or recipe. If the question requests multiple facts (e.g., both calories and protein), retrieve all requested fields.
    - For questions requesting images, photos, packaging, or visual details, retrieve the appropriate image property (e.g., `image_url`, `photo_url`, `packaging_image`, as present in schema) for the requested item.
    - For questions requesting instructions, preparation steps, or ingredients, retrieve the corresponding instruction/step/ingredient list and, if available, supporting images.
    - For questions about company practices, certifications, or sustainability, retrieve related summary information and any relevant links or references present in the schema.
    - For questions where references, external URLs, or source links are relevant, always include those properties if available.
    - When the question is about a list (e.g., "best", "top", "recommended"), retrieve multiple matching entities and sort/filter as appropriate, including their relevant details and links.
    - For numeric questions, include the value and its unit (e.g., "grams of protein").
    - For any query about images, always include the image property in the result set, if present in schema.
    - When generating UNION queries, always use the same column names and order (using AS to alias as needed) for each subquery.
    - For example:
        RETURN r.name AS name, r.description AS description, r.url AS url
        UNION
        RETURN p.name AS name, p.description AS description, p.url AS url
    Do not include explanations, apologies, or anything other than the generated Cypher statement.
    Do not answer questions that ask for anything other than creating Cypher statements.
    schema:
    {schema}
    Question: {question}
    """,
    input_variables=["schema", "question"]
)

# === Block: GraphRAG main setup and indexing ===
def main():
    neo4j_url = os.getenv("NEO4J_URL")
    neo4j_username = os.getenv("NEO4J_USERNAME")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    os.environ['OPENAI_API_KEY'] = openai_api_key
    embeddings = OpenAIEmbeddings()
    llm = ChatOpenAI(model_name="gpt-4o-mini")
    graph = Neo4jGraph(
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password
    )

    logger.info("Clearing Neo4j database...")
    graph.query("MATCH (n) DETACH DELETE n;")

    logger.info("Loading and parsing product and recipe data from blob storage...")
    products_raw = load_blob_text(PRODUCTS_BLOB)
    recipes_raw = load_blob_text(RECIPES_BLOB)
    products = parse_products(products_raw)
    recipes = parse_recipes(recipes_raw)
    logger.info(f"Parsed {len(products)} products and {len(recipes)} recipes.")

    logger.info("Loading data into Neo4j...")
    add_products_and_recipes_to_neo4j(graph, products, recipes)

    logger.info("Building Neo4j vector indices...")
    Neo4jVector.from_existing_graph(
        embedding=embeddings,
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password,
        database="neo4j",
        node_label="Product",
        text_node_properties=["name", "description", "features", "ingredients"],
        embedding_node_property="embedding",
        index_name="vector_index_product",
        keyword_index_name="entity_index_product",
        search_type="hybrid"
    )
    Neo4jVector.from_existing_graph(
        embedding=embeddings,
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password,
        database="neo4j",
        node_label="Recipe",
        text_node_properties=["name", "description", "ingredients", "instructions", "tip"],
        embedding_node_property="embedding",
        index_name="vector_index_recipe",
        keyword_index_name="entity_index_recipe",
        search_type="hybrid"
    )

    logger.info("Initializing QA Chain...")
    qa_chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=cypher_prompt,
        verbose=True,
        allow_dangerous_requests=True
    )
    logger.info("GraphRAG indexing and setup complete.")
    return qa_chain

# === Block: Module-level singleton for QA chain to avoid re-indexing on every question ===
_qa_chain = None

def get_qa_chain():
    global _qa_chain
    if _qa_chain is None:
        _qa_chain = main()
    return _qa_chain

# === Block: Public interface for answering user queries ===
def query_graph_rag(question):
    logger.info(f"Received user question: {question}")
    qa_chain = get_qa_chain()
    try:
        result = qa_chain.invoke({"query": question})["result"]
        logger.info(f"Answer: {result}")
        return result
    except Exception as e:
        logger.error(f"Error answering user question: {e}")
        return "Sorry, an error occurred while processing your question."

# === Block: CLI for manual testing ===
if __name__ == "__main__":
    logger.info("Running GraphRAG as main module.")
    qa_chain = get_qa_chain()
    question = "Show me recipes or products suitable for someone looking to reduce sugar intake."
    result = query_graph_rag(question)