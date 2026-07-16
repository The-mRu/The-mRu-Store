from fastapi import FastAPI
from backend.api import products, categories, orders, reviews, support_tickets, inventory, analytics, users, search, chat
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="The-mRu Store Chatbot API")

# Add this block to allow your frontend to talk to your backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change this to your actual frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Mount all domain routers under a clean root prefix structure
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(categories.router, prefix="/categories", tags=["Categories"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(reviews.router, prefix="/reviews", tags=["Reviews"])
app.include_router(support_tickets.router, prefix="/support-tickets", tags=["Support Tickets"])
app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(search.router, prefix="/search", tags=["Search"])
app.include_router(chat.router, prefix="/chat", tags=["Chat(AI Agent)"])

@app.get("/")
def read_root():
    return {"message": "All chatbot backend endpoints are up and running perfectly!"}



### uvicorn main_db_server:app --reload