from flask import Flask, request, jsonify
from flask_cors import CORS

# === Add your previous imports here ===
from dotenv import load_dotenv
load_dotenv()
import openai
import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
# If using beta SDK, update Vector import as needed
from azure.search.documents.models import Vector  

# === Initialize Azure Search client (reuse between requests) ===
AZURE_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
AZURE_SEARCH_KEY = os.environ["AZURE_SEARCH_KEY"]
INDEX_NAME = "nestledata"

search_client = SearchClient(
    endpoint=AZURE_SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=AzureKeyCredential(AZURE_SEARCH_KEY)
)

# === Your embedding function ===
def generate_embeddings(text):
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response["data"][0]["embedding"]

# === Flask App ===
app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return jsonify({"message": "Hello from your Flask backend!"})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")

    # --- VECTOR SEARCH IN AZURE ---
    query_embedding = generate_embeddings(user_message)
    vector = Vector(value=query_embedding, k=2, fields="embedding")
    results = search_client.search(
        search_text=None,
        vectors=[vector],
        select=["content"]
    )
    input_text = " "
    for result in results:
        input_text += result['content'] + " "

    # --- CALL OPENAI GPT ---
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Use the provided context to answer questions."},
            {"role": "user", "content": f"Context: {input_text}\n\nQuestion: {user_message}"}
        ],
        max_tokens=100,
        temperature=0
    )

    answer = response['choices'][0]['message']['content']
    return jsonify({"answer": answer})

@app.route("/log", methods=["POST"])
def log_chat():
    data = request.json
    chat = data.get("chat", [])
    print("Chat log:", chat)
    return jsonify({"status": "logged"})

if __name__ == "__main__":
    app.run(debug=True)