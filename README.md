# Adv_SRAG

Adaptive Self-RAG application built with Flask, LangGraph, Groq, Gemini embeddings, and FAISS.

The project includes:
- a landing page that explains the Self-RAG workflow
- an interactive RAG Studio for uploading PDF documents and testing grounded retrieval
- the core Self-RAG pipeline implemented with LangGraph
- an older Streamlit prototype kept in the repository as `app.py`

## Features

- Adaptive retrieval decision before vector search
- PDF ingestion with chunking and FAISS indexing
- Grounded answer generation from retrieved context
- Self-evaluation with `IsSUP` and `IsUSE`
- Automatic answer revision and query rewriting loops
- Flask web UI with landing page and interactive studio

## Project Structure

```text
adv_rag/
|-- app.py
|-- flask_app.py
|-- self_rag_pipeline.py
|-- requirements.txt
|-- setup_venv.bat
|-- templates/
|   |-- index.html
|   `-- studio.html
|-- static/
|   |-- css/
|   |   `-- styles.css
|   `-- js/
|       |-- charts.js
|       |-- script.js
|       `-- studio.js
`-- self_rag_step7.ipynb
```

## Requirements

- Python 3.10+
- Groq API key
- Google API key for Gemini embeddings

## Setup

### 1. Create and activate a virtual environment

Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Or use the included helper:

```bat
setup_venv.bat
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in both keys:

```env
GROQ_API_KEY=gsk_your_key_here
GOOGLE_API_KEY=your_google_key_here
```

## Run the Flask App

```powershell
python .\flask_app.py
```

Open:

- `http://127.0.0.1:5000/` for the landing page
- `http://127.0.0.1:5000/studio` for the interactive RAG Studio

## Run the Streamlit Prototype

```powershell
streamlit run .\app.py
```

## API Endpoints

The Flask app exposes:

- `GET /` landing page
- `GET /studio` studio page
- `GET /health` health check
- `GET /api/models` available model list
- `GET /api/status` current runtime status
- `POST /api/process-documents` upload and index PDFs
- `POST /api/reset` clear current session
- `POST /api/chat` chat response with pipeline details
- `POST /query` studio-friendly response payload

## How the Pipeline Works

`self_rag_pipeline.py` implements a LangGraph workflow with these steps:

1. Decide whether retrieval is needed.
2. Answer directly if retrieval is unnecessary.
3. Retrieve relevant document chunks from FAISS.
4. Filter document relevance.
5. Generate an answer from retrieved context.
6. Verify grounding with `IsSUP`.
7. Revise unsupported answers.
8. Verify usefulness with `IsUSE`.
9. Rewrite the query and retry when needed.

## Notes

- The current indexing path rebuilds embeddings for each new upload session.
- Uploaded files are processed through temporary files inside the Flask app.
- `.env`, `venv/`, caches, and notebook outputs should not be committed.

## Git

To initialize and push this project manually:

```powershell
git init
git branch -M main
git remote add origin https://github.com/lakshya1410/Adv_SRAG.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

If the remote already contains commits, pull or force-align carefully before pushing.