# The-mRu-Store

The-mRu-Store is a full-stack e-commerce demo project that combines a FastAPI backend, a Django storefront frontend, and an AI-powered assistant for semantic search and product support.

It is designed to showcase how a modern online store can integrate:
- product browsing and cart flows,
- user authentication and order management,
- admin management pages,
- and an AI assistant powered by retrieval-augmented generation (RAG).

## Features

- FastAPI-based backend with REST endpoints for products, search, chat, orders, auth, and support tickets
- Django-based frontend for the user shopping experience and admin dashboard
- Semantic product search using embeddings instead of simple keyword matching
- RAG-enabled assistant for answering store-related questions from ingested documents
- Admin pages for product and order management
- Support for cart, checkout, user accounts, order history, and product browsing
- AI-powered workflows for support and product assistance

## Tech Stack

- Backend: FastAPI
- Frontend: Django
- Database: SQLite for Django, with MongoDB support expected by the backend services
- AI: OpenAI + embeddings-based search
- Document processing: scripts for ingestion and vectorization
- Python packages: FastAPI, Django, Uvicorn, OpenAI, sentence-transformers, and related dependencies

## Project Structure

- [main_db_server.py](main_db_server.py) — FastAPI application entry point
- [backend/api/](backend/api/) — API modules for products, search, chat, orders, auth, users, and more
- [frontend/](frontend/) — Django project and storefront application
- [frontend/store/](frontend/store/) — templates, views, models, and frontend logic
- [agent/](agent/) — AI orchestration and tool helpers
- [scripts/](scripts/) — scripts for seeding data, embeddings, and document ingestion
- [testing/](testing/) — test scripts and API checks

## Architecture

![Project Architecture](project%20architecture.png)

The diagram above shows the high-level flow of the system, including the user-facing frontend, the FastAPI backend, the AI assistant layer, and the data/document processing pipeline.

## Getting Started

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd The-mRu-store
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the backend

From the project root:

```bash
uvicorn main_db_server:app --reload
```

The backend will be available at:
- `http://127.0.0.1:8000/docs` for FastAPI Swagger documentation
- `http://127.0.0.1:8000/` for the root API endpoint

### 5. Run the frontend

From the frontend folder:

```bash
cd frontend
python manage.py migrate
python manage.py runserver 8080
```

Then open:
- `http://127.0.0.1:8080/` for the storefront
- `http://127.0.0.1:8080/admin/` for Django admin (if enabled)

## Environment Setup

The backend may require environment variables such as:
- `OPENAI_API_KEY`
- `MONGO_URI`
- `MONGO_DB_NAME`

Create a `.env` file in the project root if needed for local development.

## Data and AI Setup

To enable full RAG functionality, run the support scripts:

```bash
python scripts/seed_data.py
python scripts/backfill_vectors.py
python scripts/ingest_docs.py
```

These scripts help populate product data, generate embeddings, and ingest documents for the AI assistant.

## How to Use

- Browse products and categories from the storefront
- Add items to the cart and proceed to checkout
- Register/login as a user to manage orders and settings
- Use the AI chat interface to ask product or policy-related questions
- Use the admin pages for store management tasks

## Development Notes

- The FastAPI backend is the main API layer for search and chat features.
- The Django frontend handles the visual storefront and user/admin pages.
- The AI assistant depends on document ingestion and vector embeddings for accurate answers.
- If local features are not working, verify that MongoDB and required environment variables are available.


