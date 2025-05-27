import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv, set_key
ENV_PATH = ".env"
load_dotenv(ENV_PATH)

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from functions.vector_rag import query_vector_rag
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
CORS(app)

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
    elif AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY:
        rag_mode = "vector"
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=INDEX_NAME,
            credential=AzureKeyCredential(AZURE_SEARCH_KEY)
        )
    else:
        rag_mode = None

def run_scraping_jobs():
    try:
        from functions import scrape_nestle_products
        from functions import scrape_nestle_recipes

        scrape_nestle_products.main()
        scrape_nestle_recipes.main()

        return True
    except Exception as e:
        return False

def run_file_processing():
    try:
        from functions import file_processing
        file_processing.main()
        return True
    except Exception as e:
        return False

def run_vector_rag_indexing():
    try:
        from functions import vector_rag
        vector_rag.main()
        return True
    except Exception as e:
        return False

def run_graph_rag_indexing():
    try:
        from src.api.functions import graph_rag
        graph_rag.main()
        return True
    except Exception as e:
        return False

def generate_embeddings(text):
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

def graph_rag_query(user_message):
    try:
        from langchain_openai import ChatOpenAI
        from langchain_community.graphs import Neo4jGraph
        from langchain.prompts import PromptTemplate
        from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain

        llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=os.getenv("OPENAI_API_KEY"))
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
        return "Sorry, something went wrong with the graph-based query."

@app.route("/")
def home():
    return jsonify({"message": "Hello from your Flask backend!"})

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

    os.environ['BOT_NAME'] = name
    os.environ['BOT_ICON'] = icon
    os.environ['BOT_COLOR'] = color
    set_key(ENV_PATH, 'BOT_NAME', name)
    set_key(ENV_PATH, 'BOT_ICON', icon)
    set_key(ENV_PATH, 'BOT_COLOR', color)

    return jsonify({
        "status": "success",
        "bot_name": name,
        "bot_icon": icon,
        "bot_color": color
    }), 200

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
            answer = query_vector_rag(user_message, INDEX_NAME)
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"status": "error", "message": "Failed to generate answer."}), 500

if __name__ == "__main__":
    select_rag_mode()
    if not rag_mode:
        exit(1)
    app.run(debug=False, host="0.0.0.0")