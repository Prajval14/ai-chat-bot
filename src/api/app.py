# === Import Libraries and Set Up Logging ===
import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv, set_key
ENV_PATH = ".env"
load_dotenv(ENV_PATH)

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
# from azure.search.documents.models import Vector

from openai import OpenAI

# === Initialize Logging ===
LOG_FILENAME = "backend_chatbot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILENAME, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# === Load Environment Variables ===
load_dotenv()

# === Flask Application Initialization ===
app = Flask(__name__)
CORS(app)

# === Global State for Credentials and Mode Selection ===
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
INDEX_NAME = "nestledata"
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

rag_mode = None
search_client = None

def select_rag_mode():
    global rag_mode, search_client
    if NEO4J_URI and NEO4J_USERNAME and NEO4J_PASSWORD:
        rag_mode = "graph"
        logging.info("GraphRAG mode selected (Neo4j credentials detected)")
    elif AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY:
        rag_mode = "vector"
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=INDEX_NAME,
            credential=AzureKeyCredential(AZURE_SEARCH_KEY)
        )
        logging.info("VectorRAG mode selected (Azure Search credentials detected)")
    else:
        rag_mode = None
        logging.error("No valid RAG credentials found in environment variables.")

# === Data Scraping Step ===
def run_scraping_jobs():
    try:
        from functions import scrape_nestle_products
        from functions import scrape_nestle_recipes

        scrape_nestle_products.main()
        scrape_nestle_recipes.main()

        logging.info("Scraping jobs completed successfully.")
        return True
    except Exception as e:
        logging.error(f"Error in scraping jobs: {e}")
        return False

# === File Processing Step ===
def run_file_processing():
    try:
        from functions import file_processing
        file_processing.main()
        logging.info("File processing completed successfully.")
        return True
    except Exception as e:
        logging.error(f"Error in file processing: {e}")
        return False

# === VectorRAG Indexing Step ===
def run_vector_rag_indexing():
    try:
        from functions import vector_rag_indexing
        vector_rag_indexing.main()
        logging.info("Vector RAG indexing completed successfully.")
        return True
    except Exception as e:
        logging.error(f"Error in Vector RAG indexing: {e}")
        return False

# === GraphRAG Indexing Step ===
def run_graph_rag_indexing():
    try:
        from functions import graph_rag_indexing
        graph_rag_indexing.main()
        logging.info("Graph RAG indexing completed successfully.")
        return True
    except Exception as e:
        logging.error(f"Error in Graph RAG indexing: {e}")
        return False

# === Embedding Function for VectorRAG ===
def generate_embeddings(text):
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

# === VectorRAG Query Function ===
def vector_rag_query(user_message, search_client):
    # 1. Generate embedding for user query
    query_embedding = generate_embeddings(user_message)

    # 2. Vector search with latest SDK (using dict format for vectors parameter)
    results = search_client.search(
        search_text=None,
        vectors=[{
            "value": query_embedding,
            "k": 2,
            "fields": "embedding"
        }],
        select=["content"]
    )

    # 3. Concatenate search results
    input_text = " ".join(result['content'] for result in results if 'content' in result)

    # 4. Call OpenAI with RAG context
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer questions."},
            {"role": "user", "content": f"Context: {input_text}\n\nQuestion: {user_message}"}
        ],
        max_tokens=100,
        temperature=0
    )
    answer = response.choices[0].message.content
    return answer

# === GraphRAG Query Function ===
def graph_rag_query(user_message):
    try:
        from langchain_openai import ChatOpenAI
        from langchain_community.graphs import Neo4jGraph
        from langchain.prompts import PromptTemplate
        from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain

        llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=OPENAI_API_KEY)
        graph = Neo4jGraph(
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD
        )
        schema = graph.get_schema

        template = """
        Task: Generate a Cypher statement to query the graph database.
        Instructions:
        Use only relationship types and properties provided in schema.
        Do not use other relationship types or properties that are not provided.
        schema:
        {schema}
        Note: Do not include explanations or apologies in your answers.
        Do not answer questions that ask anything other than creating Cypher statements.
        Do not include any text other than generated Cypher statements.
        Question: {question}
        """
        question_prompt = PromptTemplate(
            template=template,
            input_variables=["schema", "question"]
        )
        qa = GraphCypherQAChain.from_llm(
            llm=llm,
            graph=graph,
            cypher_prompt=question_prompt,
            verbose=False,
            allow_dangerous_requests=True
        )
        result = qa.invoke({"query": user_message})
        return result['result']
    except Exception as e:
        logging.error(f"Error in GraphRAG querying: {e}")
        return "Sorry, something went wrong with the graph-based query."

# === Root Endpoint ===
@app.route("/")
def home():
    return jsonify({"message": "Hello from your Flask backend!"})

# === Initialization Endpoint ===
@app.route("/init", methods=["POST"])
def init():
    select_rag_mode()
    if not rag_mode:
        return jsonify({"status": "error", "message": "No valid RAG credentials found."}), 500

    scraping_ok = run_scraping_jobs()
    if not scraping_ok:
        return jsonify({"status": "error", "message": "Scraping failed."}), 500

    file_processing_ok = run_file_processing()
    if not file_processing_ok:
        return jsonify({"status": "error", "message": "File processing failed."}), 500

    if rag_mode == "graph":
        index_ok = run_graph_rag_indexing()
    else:
        index_ok = run_vector_rag_indexing()
    if not index_ok:
        return jsonify({"status": "error", "message": "Indexing failed."}), 500

    return jsonify({"status": "success", "mode": rag_mode})

@app.route('/bot-config', methods=['GET'])
def get_bot_config():
    return jsonify({
        "bot_name": os.getenv('BOT_NAME', ''),
        "bot_icon": os.getenv('BOT_ICON', ''),
        "bot_color": os.getenv('BOT_COLOR', '')
    })

@app.route('/bot-config', methods=['POST'])
def edit_bot_config():
    data = request.json
    name = data.get('bot_name', '')
    icon = data.get('bot_icon', '')
    color = data.get('bot_color', '')

    # Optionally, sanitize/check input here

    os.environ['BOT_NAME'] = name
    os.environ['BOT_ICON'] = icon
    os.environ['BOT_COLOR'] = color
    set_key(ENV_PATH, 'BOT_NAME', name)
    set_key(ENV_PATH, 'BOT_ICON', icon)
    set_key(ENV_PATH, 'BOT_COLOR', color)

    logging.info(f"Bot config updated: name={name}, icon={icon}, color={color}")

    return jsonify({
        "status": "success",
        "bot_name": name,
        "bot_icon": icon,
        "bot_color": color
    }), 200

# === Chat Endpoint ===
@app.route("/chat", methods=["POST"])
def chat():
    select_rag_mode()
    if not rag_mode:
        return jsonify({"status": "error", "message": "No valid RAG credentials found."}), 500

    data = request.json
    user_message = data.get("message", "")
    try:
        if rag_mode == "graph":
            answer = graph_rag_query(user_message)
        else:
            answer = vector_rag_query(user_message)
        return jsonify({"answer": answer})
    except Exception as e:
        logging.error(f"Error in chat endpoint: {e}")
        return jsonify({"status": "error", "message": "Failed to generate answer."}), 500

# === Start Flask Application ===
if __name__ == "__main__":
    select_rag_mode()
    if not rag_mode:
        logging.error("No valid RAG credentials found. Exiting app startup.")
        exit(1)
    app.run(debug=False, host="0.0.0.0")