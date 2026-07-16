
# The-mRu-Store 🛒🤖  
### AI-Powered E-Commerce Backend with Semantic Search & RAG Chat Assistant

A production‑ready e‑commerce backend built with **FastAPI**, **MongoDB**, and **OpenAI**.  
It features a **Retrieval-Augmented Generation (RAG)** chat assistant that answers product, stock, and policy questions using semantic search and real‑time tool calling.

---

## ✨ Key Features

- **Semantic Product Search** – find items by meaning, not just keywords (via sentence‑transformers).
- **Real‑time Stock & Product Info** – exact lookups via product ID.
- **Policy Q&A** – ask about shipping, returns, warranties – answers come from ingested store policy documents (PDF/Word).
- **Support Ticket Creation** – automatically generate tickets for human review.
- **Async & Fast** – non‑blocking I/O with FastAPI and Motor (MongoDB async driver).

---

## 🧱 Architecture Overview

| Component               | Technology                               |
|-------------------------|------------------------------------------|
| Web Framework           | FastAPI (async)                          |
| Database                | MongoDB (via Motor)                      |
| AI Orchestration        | OpenAI `gpt-4o-mini` (native tool calls) |
| Vector Embeddings       | `all-MiniLM-L6-v2` (384‑dim)            |
| Similarity Search       | Cosine similarity                        |
| Document Ingestion      | PDF & Word parsing → chunking → vectorise|
| Frontend (test UI)      | Static `index.html`                      |

---

## 🛠️ Local Setup & Installation

### 1. Prerequisites
- Python 3.9+
- MongoDB running locally on `mongodb://localhost:27017`
- An [OpenAI API key](https://platform.openai.com/account/api-keys)

### 2. Clone & Virtual Environment
```bash
git clone <your-repo-url>
cd the-mru-store
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Variables
Create a `.env` file in the project root with the following (see `.env.example`):

```
OPENAI_API_KEY=your_openai_api_key_here
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=amazon_clone_db
API_BASE_URL=http://127.0.0.1:8000
```

---

## 🧠 Database Seeding & AI Setup

Before starting the server, you must populate the vector indices.

### Backfill Product Embeddings
This computes 384‑dim vectors for all existing products in MongoDB, enabling semantic search.

```bash
python scripts/backfill_vectors.py
```

### Ingest Store Policies
Scans `docs/static/` for PDFs and Word documents, chunks the text, and stores vectorised knowledge.

```bash
python scripts/ingest_docs.py
```

---

## 💻 Running the Application

Start the FastAPI server with live reload:

```bash
uvicorn main_db_server:app --reload
```

- **API Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)  
- **Chat UI:** Open `index.html` in your browser to interact with the AI assistant.

---

## 🤖 AI Agent Capabilities (Tools)

The chat assistant is tightly bound to e‑commerce operations. It detects user intent and invokes the appropriate backend tools:

| Tool | Description |
|------|-------------|
| `ai_omni_search` | Vector‑based semantic product search (conceptual matching) |
| `get_product_by_id` | Retrieve exact product details and current stock |
| `search_store_policy` | Answer policy questions using ingested documents |
| `create_support_ticket` | Generate a new support ticket in the database for human follow‑up |

---

<!-- ## 📁 Project Structure (simplified)

```
.
├── main_db_server.py         # FastAPI app entry
├── scripts/
│   ├── backfill_vectors.py   # Generate product embeddings
│   └── ingest_docs.py        # Ingest policy files into vector store
├── docs/static/              # Store policies (PDF, .docx)
├── index.html                # Chat UI test page
├── .env.example
└── requirements.txt
``` -->

---

## 🧪 Testing the API

You can test endpoints via Swagger UI or with `curl`.  
Example: semantic search for `"comfortable running shoes"`:

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "comfortable running shoes"}'
```

---
<!-- 
## 🚀 Deployment

For production, consider:
- Using a cloud MongoDB (Atlas)
- Setting up a process manager (e.g., Gunicorn with Uvicorn workers)
- Securing your `.env` and using HTTPS
- Using a vector database (Pinecone, Weaviate) for larger scales

--- -->


---

## 🙌 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

**Happy Building!** 🛍️


