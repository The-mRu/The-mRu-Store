# The-mRu-Store

The-mRu-Store is a full-stack e-commerce demo project that combines a FastAPI backend, a Django storefront frontend, and an AI-powered assistant for semantic search, customer support, and admin analytics.

It is designed to showcase how a modern online store can integrate:
- product browsing and cart flows,
- user authentication and order management,
- admin management pages,
- and an **agentic AI assistant** — one for customers, one for admins — built on OpenAI function-calling with a multi-round tool-use loop.

## Features

- FastAPI-based backend with REST endpoints for products, search, chat, orders, cart, support tickets, reviews, recommendations, and admin analytics
- Django-based frontend for the customer storefront and admin dashboard
- Hybrid product search: keyword (`$text`) + vector (sentence-transformer embeddings), merged via Reciprocal Rank Fusion, with category/brand/gender/price filtering
- **Customer AI assistant** — 20 tools covering product discovery, recommendations/comparisons, order tracking, support tickets, and personalized recommendations, with a persistent product-ID registry that prevents the model from fabricating product IDs across a conversation
- **Admin AI assistant** — a separate, admin-gated tool set for business intelligence: sales summaries, sales analytics, top-selling products, per-product performance analysis, and inventory alerts — all with flexible natural-language date parsing (`"today"`, `"last week"`, `"July 28, 2026"`, `"2 days ago"`, exact dates, or full ranges) instead of rigid enums
- Multi-round agentic loop: the model can call a tool, inspect the result, and call further tools in the same turn — enabling self-correction (e.g., resolving a product name to a real ID before analyzing it) without waiting for the next user message
- Support for cart, checkout, user accounts, order history, and product browsing

## Tech Stack

- Backend: FastAPI (async, via Motor for MongoDB)
- Frontend: Django
- Database: MongoDB (`amazon_clone_db`) as the primary data store; SQLite may still back Django's own session/auth tables
- AI: OpenAI function-calling (`gpt-4o-mini`) + sentence-transformer embeddings for semantic search
- Document processing: scripts for ingestion, vectorization, and data cleanup
- Python packages: FastAPI, Django, Uvicorn, OpenAI, sentence-transformers, Motor, and related dependencies



## Architecture

![Project Architecture](project%20architecture.png)

The diagram above shows the high-level flow of the system: the user-facing frontend, the FastAPI backend, the AI assistant layer (customer and admin), and the data/document processing pipeline.

## AI Assistant Overview

### Customer assistant
Handles product discovery, comparisons, recommendations, order status, and support tickets, scoped to the logged-in user's session. A product-ID registry tracks every product returned by prior tool calls in a conversation, so the assistant can only reference real IDs — never guessed ones — when looking up reviews, comparisons, or similar items.

### Admin assistant
A separate, permission-gated assistant (verified server-side against the `Admins` collection) for store-management questions like:
- "What's our revenue today / this week / for a specific date range?"
- "What are our best-selling products this month?"
- "Why isn't [product] selling well?"
- "What's out of stock or at risk of stocking out soon?"

Product-specific questions are resolved in two steps — the assistant first looks up the real product ID from the name mentioned, then requests performance data using that ID, rather than guessing an ID directly.

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

To enable full search and AI functionality, run the support scripts:

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
- Use the customer AI chat to ask product or policy-related questions
- Log in as an admin to use the admin AI assistant for business and product analytics
- Use the admin pages for store management tasks

## Development Notes

- The FastAPI backend is the main API layer for search, chat, orders, and admin analytics.
- The Django frontend handles the visual storefront and user/admin pages.
- The AI assistants depend on document ingestion and vector embeddings for accurate answers.
- Product-ID resolution and tool dispatch logic are handled in code (not just prompting) to keep the assistants reliable — see `agent/orchestrator.py`.
- If local features are not working, verify that MongoDB and required environment variables are available.