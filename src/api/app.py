# ==== Standard Library Imports ====
import os

# ==== Flask and CORS ====
from flask import Flask, request, jsonify
try:
    from flask_cors import CORS, cross_origin  # The typical way to import flask-cors
except ImportError:
    # Path hack allows examples to be run without installation.
    import os
    parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.sys.path.insert(0, parentdir)
    from flask_cors import CORS, cross_origin

# ==== Environment Variable Management ====
from dotenv import load_dotenv, set_key

# ==== Azure SDK Imports ====
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

# ==== OpenAI SDK Import ====
from openai import OpenAI

# ==== Logging Utilities ====
from functions.log_utils import get_blob_logger
logger = get_blob_logger(__name__)

# ==== Load Environment Variables ====
load_dotenv()

# ==== Flask App Initialization ====
app = Flask(__name__)
CORS(app)

# ==== Global Config & Client Initialization ====
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
INDEX_NAME = "nestledata"
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

rag_mode = None
search_client = None

# ==== Helper Functions ====
def select_rag_mode():
    global rag_mode, search_client
    logger.info("Selecting RAG mode...")
    if NEO4J_URI and NEO4J_USERNAME and NEO4J_PASSWORD:
        rag_mode = "graph"
        logger.info("RAG mode set to 'graph' (Neo4j).")
    elif AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY:
        rag_mode = "vector"
        logger.info("RAG mode set to 'vector' (Azure Search).")
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=INDEX_NAME,
            credential=AzureKeyCredential(AZURE_SEARCH_KEY)
        )
    else:
        rag_mode = None
        logger.warning("No valid RAG credentials found.")

def run_scraping_jobs():
    try:
        from functions import scrape_nestle_products
        from functions import scrape_nestle_recipes
        logger.info("Running scraping jobs...")
        scrape_nestle_products.main()
        scrape_nestle_recipes.main()
        logger.info("Scraping jobs completed successfully.")
        return True
    except Exception as e:
        logger.error(f"Scraping jobs failed: {e}")
        return False

def run_file_processing():
    try:
        from functions import file_processing
        logger.info("Running file processing...")
        file_processing.main()
        logger.info("File processing completed successfully.")
        return True
    except Exception as e:
        logger.error(f"File processing failed: {e}")
        return False

def run_vector_rag_indexing():
    try:
        from functions import vector_rag
        logger.info("Running vector RAG indexing...")
        vector_rag.main()
        logger.info("Vector RAG indexing completed successfully.")
        return True
    except Exception as e:
        logger.error(f"Vector RAG indexing failed: {e}")
        return False

def run_graph_rag_indexing():
    try:
        from functions import graph_rag
        logger.info("Running graph RAG indexing...")
        graph_rag.main()
        logger.info("Graph RAG indexing completed successfully.")
        return True
    except Exception as e:
        logger.error(f"Graph RAG indexing failed: {e}")
        return False

# ==== API Endpoints ====

## Health Check Endpoint
@app.route("/")
def home():
    logger.info("Health check at '/' endpoint.")
    return jsonify({"message": "Hello from your Flask backend!"})

## Initialization Endpoint
@app.route("/init", methods=["POST"])
def init():
    select_rag_mode()
    if not rag_mode:
        logger.error("No valid RAG credentials found during /init.")
        return jsonify({"status": "error", "message": "No valid RAG credentials found."}), 500

    scraping_ok = run_scraping_jobs()
    if not scraping_ok:
        logger.error("Scraping failed during /init.")
        return jsonify({"status": "error", "message": "Scraping failed."}), 500

    file_processing_ok = run_file_processing()
    if not file_processing_ok:
        logger.error("File processing failed during /init.")
        return jsonify({"status": "error", "message": "File processing failed."}), 500

    if rag_mode == "graph":
        index_ok = run_graph_rag_indexing()
    else:
        index_ok = run_vector_rag_indexing()
    if not index_ok:
        logger.error("Indexing failed during /init.")
        return jsonify({"status": "error", "message": "Indexing failed."}), 500

    logger.info(f"Initialization completed successfully in {rag_mode} mode.")
    return jsonify({"status": "success", "mode": rag_mode})

## Bot Config Endpoints
@app.route('/bot-config', methods=['GET'])
def get_bot_config():
    logger.info("Received GET request for bot config.")
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

    os.environ['BOT_NAME'] = name
    os.environ['BOT_ICON'] = icon
    os.environ['BOT_COLOR'] = color
    set_key('./.env', 'BOT_NAME', name)
    set_key('./.env', 'BOT_ICON', icon)
    set_key('./.env', 'BOT_COLOR', color)
    logger.info(f"Bot config updated: name={name}, icon={icon}, color={color}")

    return jsonify({
        "status": "success",
        "bot_name": name,
        "bot_icon": icon,
        "bot_color": color
    }), 200

## Chat Endpoint
@app.route("/chat", methods=["POST"])
def chat():
    select_rag_mode()
    if not rag_mode:
        logger.error("No valid RAG credentials found for chat.")
        return jsonify({"status": "error", "message": "No valid RAG credentials found."}), 500

    data = request.json
    user_message = data.get("message", "")

    try:
        if rag_mode == "graph":
            from functions.graph_rag import query_graph_rag
            answer = query_graph_rag(user_message)
        else:
            from functions.vector_rag import query_vector_rag
            answer = query_vector_rag(user_message, INDEX_NAME)
        logger.info("Chat answer generated successfully.")
        return jsonify({"answer": answer})
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"Error during chat handling: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

# ==== Main Entrypoint ====
if __name__ == "__main__":
    select_rag_mode()
    if not rag_mode:
        logger.error("Failed to start Flask app due to missing RAG credentials.")
        exit(1)
    logger.info("Starting Flask app...")
    app.run(debug=True, host="0.0.0.0")