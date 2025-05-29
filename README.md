---
page_type: sample
languages:
- python
- javascript
- typescript
- html
- bicep
products:
- azure
- azure-cognitive-search
- azure-blob-storage
- azure-app-service
- openai
- neo4j
urlFragment: nestle-ai-chatbot
name: React + Python AI Chatbot with Azure Search, Blob Storage, and Neo4j
description: Full-stack AI chatbot with a Python (Flask) backend and React (Vite) frontend, leveraging Azure Cognitive Search, Blob Storage, OpenAI, and Neo4j for RAG capabilities.
---

# React + Python AI Chatbot with Azure Search, Blob Storage, and Neo4j

This sample provides a blueprint for a production-grade, Retrieval-Augmented Generation (RAG) chatbot using a Python (Flask) backend, a React (Vite) frontend, and integration with Azure Cognitive Search, Blob Storage, OpenAI, and Neo4j. The template is suitable for enterprise and research settings, and is extensible for additional cloud services.

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