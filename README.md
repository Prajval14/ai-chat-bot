# React + Python AI Powered RAG Chatbot with Azure Cognitive Search and Neo4j Graph

This project provides a blueprint for a production-grade, Retrieval-Augmented Generation (RAG) chatbot using a Python (Flask) backend, a React (Vite) frontend, and integration with Azure Cognitive Search, Blob Storage, OpenAI, and Neo4j.

---

## Table of Contents

- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
  - [Python Backend](#python-backend)
  - [React + Vite Frontend](#react--vite-frontend)
- [Environment Variables](#environment-variables)
  - [Backend (.env)](#backend-env)
  - [Frontend (.env)](#frontend-env)
- [Setup Instructions](#setup-instructions)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Security and Secrets](#security-and-secrets)
- [Reporting Issues](#reporting-issues)

---

## Project Structure

/src
/api # Python Flask backend
/web # React + Vite frontend
.env.sample # Environment variable template for backend

---

## Prerequisites

### Python Backend

- Python 3.9 or higher
- pip (Python package manager)
- Virtual environment tool (recommended: `venv`)
- Access to Azure Cognitive Search, Azure Blob Storage, OpenAI API, and Neo4j DB

**Python dependencies:**
- Flask
- Flask-CORS
- python-dotenv
- openai
- azure-storage-blob
- azure-search-documents
- neo4j
- langchain
- playwright (for scraping, optional)
- Any other dependencies as listed in `requirements.txt`

---

### React + Vite Frontend

- Node.js (v18 or higher)
- npm or yarn

**Frontend dependencies:**
- React
- Vite
- axios (or use native fetch)
- Any other dependencies as listed in `package.json`

---

## Environment Variables

### Backend `.env`

Copy `.env.sample` to `.env` in the `/src/api` directory and fill in the required credentials:

AZURE_SEARCH_ENDPOINT={{AZURE_SEARCH_ENDPOINT}}
AZURE_SEARCH_KEY={{AZURE_SEARCH_KEY}}

AZURE_STORAGE_CONNECTION_STRING={{AZURE_STORAGE_CONNECTION_STRING}}
AZURE_BLOB_CONTAINER=files

OPENAI_API_KEY={{OPENAI_API_KEY}}

NEO4J_URI={{NEO4J_URI}}
NEO4J_USERNAME={{NEO4J_USERNAME}}
NEO4J_PASSWORD={{NEO4J_PASSWORD}}

BOT_NAME='NestleBot'
BOT_ICON=''
BOT_COLOR='#306D51'


> Replace `{{...}}` placeholders with your actual values.

---

### Frontend `.env`

Copy `.env.sample` to `.env` in the `/src/web` directory and set the following:

Example for local development:
VITE_API_URL=http://localhost:5000

---

## Bot Configuration

After deployment, you can customize your bot’s appearance and identity (such as name, icon, and theme color) using the web interface:

1. **Navigate to the frontend application** in your browser.  
   - For local development:  
     `http://localhost:5173/settings`  
     or  
     `http://localhost:5173` and use the navigation to access bot settings.

2. **Update the bot’s name, icon, and color** in the settings form.

3. **Save changes**. The backend will automatically update the configuration and persist the settings.

---

## Retrieval-Augmented Generation (RAG) Modes

This application supports two RAG modes for answering user queries: **Vector RAG** and **Graph RAG**.  
The mode is automatically selected at backend startup based on available credentials in your `.env` file.

### What’s the Difference?

- **Vector RAG (Azure Cognitive Search):**  
  Uses Azure Cognitive Search to perform semantic search over ingested document chunks. Best suited for fast, scalable, keyword or embedding-based retrieval and Q&A over large volumes of unstructured text (such as documents or articles).

- **Graph RAG (Neo4j):**  
  Uses a Neo4j graph database to represent and query relationships between entities (such as recipes, products, ingredients). Best for complex queries that require traversing relationships, recommendations, or multi-hop reasoning.

### How to Set the Mode

- **To enable Graph RAG:**  
  - Set all three of these environment variables in your backend `.env` file:
    ```
    NEO4J_URI={{NEO4J_URI}}
    NEO4J_USERNAME={{NEO4J_USERNAME}}
    NEO4J_PASSWORD={{NEO4J_PASSWORD}}
    ```
  - If these are set and valid, the backend will use Neo4j Graph RAG automatically.

- **To enable Vector RAG:**  
  - Set these environment variables in your backend `.env` file:
    ```
    AZURE_SEARCH_ENDPOINT={{AZURE_SEARCH_ENDPOINT}}
    AZURE_SEARCH_KEY={{AZURE_SEARCH_KEY}}
    ```
  - The backend will use Vector RAG if Neo4j credentials are **not** provided but Azure Search credentials are.

- **If neither set:**  
  - The backend will not enable RAG and will log a warning. Please supply at least one set of valid credentials.

> If both Neo4j and Azure Search credentials are provided, **Graph RAG** (Neo4j) takes precedence.

---

## Scraping Limits and Token Usage

By default, scraping scripts in this project limit the number of products and recipes ingested to minimize API/token usage:

products = products[:3]  # Only process first 3 products
recipes = recipes[:3]    # Only process first 3 recipes
total_pages = min(total_pages, 0)  # Restrict pagination
To process all items, remove or comment out these lines in the scraping scripts.
You may also increase the numbers or pagination limit as needed for your use case.

Adjust these limits according to your API budget or testing needs.

---

## Setup Instructions

### Backend Setup

1. **Install Python dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

2. **Set up environment variables:**
    - Copy `.env.sample` to `.env`
    - Edit `.env` and fill in your Azure/OpenAI/Neo4j credentials

3. **Run the backend server:**
    ```bash
    python app.py
    ```
    By default, the backend will run at `http://localhost:5000`.

---

### Frontend Setup

1. **Install Node.js dependencies:**
    ```bash
    npm install
    ```

2. **Set up environment variables:**
    - Copy `.env.sample` to `.env`
    - Set `VITE_API_URL` to the backend URL (`http://localhost:5000` for local)

3. **Run the frontend development server:**
    ```bash
    npm run dev
    ```
    By default, the frontend will run at `http://localhost:5173`.

---

## Security and Secrets

This sample uses environment variables to store all secrets and connection strings. **Never commit `.env` files or any secrets to your repository.** For production deployments, consider using Azure Key Vault or other secure secret management solutions.

---

## Reporting Issues

If you encounter any issues, have suggestions, or wish to contribute, please file an issue or pull request on this repository.

---
