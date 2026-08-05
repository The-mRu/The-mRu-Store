# The-mRu-Store

The-mRu-Store is an experimental, chat-first e-commerce demo focused on the AI assistants (customer and admin). The frontend is intentionally minimal — the primary surface is the FastAPI-based chat API and the multi-round agent loop implemented in `agent/orchestrator.py`.

Purpose: provide a well-scoped environment to build and evaluate conversational RAG agents that interact with product data, recommendations, orders, and support workflows.

## Features (chat-first)

- Chat-first architecture: FastAPI chat endpoints and agent loop are the main integration surface.
- Rich customer AI assistant: tools for discovery, comparisons, recommendations, order tracking, and support tickets; product-ID registry prevents fabrication of IDs.
- Admin AI assistant: permission-gated analytics tools for revenue, top-selling items, stock alerts, and flexible date parsing.
- Hybrid search backing the assistant: keyword + vector search (sentence-transformer embeddings) with filters and rank fusion.
- Multi-round agent loop: model can call tools, inspect responses, and call additional tools in the same turn for robust, self-correcting behavior.

Frontend: minimal storefront provided for manual testing and demoing chat flows — not the project's core focus.

## Tech Stack

- Backend: FastAPI (async, via Motor for MongoDB)
- Frontend: Django
- Database: MongoDB (`amazon_clone_db`) as the primary data store; SQLite may still back Django's own session/auth tables
- AI: OpenAI function-calling (`gpt-4o-mini`) + sentence-transformer embeddings for semantic search
- Document processing: scripts for ingestion, vectorization, and data cleanup
- Python packages: FastAPI, Django, Uvicorn, OpenAI, sentence-transformers, Motor, and related dependencies



## Architecture
 User → Django Frontend → FastAPI Backend → MongoDB → AI Agent (OpenAI + sentence-transformers) → Response

![Project Architecture](project%20architecture.png)

The diagram above shows the high-level flow of the system: the user-facing frontend, the FastAPI backend, the AI assistant layer (customer and admin), and the data/document processing pipeline.

## AI Assistant Overview (concise)

Customer assistant
- Handles product discovery, comparisons, recommendations, order status, and support tickets. Conversation state includes a product-ID registry to avoid fabricated IDs.

Admin assistant
- Permission-gated assistant for BI-style queries (revenue, best-sellers, stock alerts). Admin requests are validated server-side against the `Admins` collection.

Note: tool dispatch and product-ID resolution are implemented in code (see `agent/orchestrator.py`) to reduce prompt brittleness.
## Tool Inventory

### Customer Tools (24)
| Pillar | Tools |
|--------|-------|
| Product Discovery | `ai_omni_search`, `get_product_by_id`, `list_categories`, `list_brands`, `get_product_reviews` |
| Recommendations | `recommend_products`, `compare_products`, `get_similar_products` |
| Cart & Checkout | `manage_cart` |
| Orders | `check_order_status`, `get_user_orders`, `get_order_items` |
| Support Tickets | `create_support_ticket`, `check_ticket_status`, `add_ticket_comment`, `close_support_ticket`, `escalate_ticket`, `get_user_tickets` |
| Personalization | `remember_preference`, `get_user_preferences`, `get_personalized_recommendations`, `get_recently_discussed` |
| Store Policy | `search_store_policy` |

### Admin Tools (8)
| Category | Tools |
|----------|-------|
| Dashboard | `get_business_summary`, `get_sales_analytics` |
| Products | `get_top_selling_products`, `get_product_performance` |
| Inventory | `get_inventory_alerts` |
| Orders | `get_order_status_breakdown` |
| Tickets | `get_pending_tickets_summary` |
| Business Queries | `natural_language_business_query` |

**Total: 32 tools** across 6 pillars (Discovery, Cart, Orders, Support, Personalization, Admin).
## Quickstart — Chat-first (local)

1. Clone and enter:

```bash
git clone <your-repo-url>
cd The-mRu-store
```

2. Create & activate a venv (Windows example):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Install Python deps:

```bash
pip install -r requirements.txt
```

4. Provide secrets via `.env` or environment variables (see `.env.example`). Minimal required keys:

- `OPENAI_API_KEY`
- `MONGO_URI` (optional for demo but recommended)
- `MONGO_DB_NAME`

5. Start the backend (agent + chat endpoints):

```bash
uvicorn main_db_server:app --reload
```

6. Explore the API and chat endpoints at:

- `http://127.0.0.1:8000/docs` (OpenAPI) — use this to find the live chat endpoints

Example: a generic chat POST (adjust path per your API):

```bash
curl -X POST "http://127.0.0.1:8000/api/chat" -H "Content-Type: application/json" -d '{"user_id":"user@example.com","message":"Show me running shoes under $100"}'
```

Frontend (optional demo):

```bash
cd frontend
python manage.py migrate
python manage.py runserver 8080
```

Visit `http://127.0.0.1:8080/` for the minimal storefront and `http://127.0.0.1:8080/admin/` for Django admin.

## Environment Setup

The backend requires a few environment variables. Create a `.env` in the project root or export these variables in your shell. See the included `.env.example` for guidance.

Required (or strongly recommended):
- `OPENAI_API_KEY` — required for full chat/assistant functionality
- `MONGO_URI` — recommended (if omitted, some features run in demo mode)
- `MONGO_DB_NAME`

Security: never commit real API keys to version control. Use a secrets manager or CI encrypted variables for production.


## Data and AI Setup

Populate sample data and generate vectors used by the assistant:

```bash
python scripts/seed_data.py          # seeds products, users, orders (demo)
python scripts/backfill_vectors.py   # compute or recompute product embeddings
python scripts/ingest_docs.py        # ingest support docs for RAG
```

If you do not run the above, the assistant may operate in a limited/demo mode.

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

## Key Design Decisions

- **Product-ID Registry**: The orchestrator maintains a server-side registry of every product ID mentioned in a conversation. Tool calls with fabricated IDs are intercepted and corrected before hitting the backend — no prompt-based guardrail needed.
- **Multi-Round Tool Loop**: The agent can call tools, inspect responses, and call additional tools within the same turn (up to 4 rounds). This enables self-correction when a tool call fails or returns an unexpected result.
- **Hybrid Search**: Combines keyword matching (field-weighted scoring) with semantic search (sentence-transformer embeddings) using Reciprocal Rank Fusion. Hard filters (brand, category, price) are applied before similarity scoring.
- **Flexible Date Parsing**: Admin analytics accept natural language dates ("yesterday", "last month", "July 28, 2026") via a single `parse_date()` function used consistently across all admin endpoints.
