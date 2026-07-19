from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
from backend.db.database import db
import uuid
import datetime

router = APIRouter()

# --- PYDANTIC MODELS ---
class OrderRequest(BaseModel):
    user_id: str
    items: List[Dict[str, Any]]
    shipping: Dict[str, str]
    total: float

# --- YOUR EXISTING ENDPOINTS (With standardized field names) ---

@router.get("/")
async def get_all_orders():
    """Retrieve all orders (Admin only ideally)."""
    orders = await db.Orders.find({}, {"_id": 0}).to_list(length=100)
    return orders

@router.get("/{order_id}/status")
async def get_order_status(order_id: str):
    """Check the status of a specific order."""
    # Note: Updated "id" to "order_id" to match insertion logic
    order = await db.Orders.find_one({"order_id": order_id}, {"_id": 0, "status": 1})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.get("/user/{user_id}")
async def get_user_orders(user_id: str):
    """Retrieve all orders for a specific user."""
    # Note: Updated "userId" to "user_id" to match insertion logic
    orders = await db.Orders.find({"user_id": user_id}, {"_id": 0}).to_list(length=100)
    
    if not orders:
        raise HTTPException(status_code=404, detail="No orders found for this user")
        
    return orders

# --- THE NEW CHECKOUT ENDPOINT ---

@router.post("/place")
async def place_order(order: OrderRequest):
    """Places a new order and clears the user's active cart."""
    # 1. Create the order document
    order_data = {
        "order_id": str(uuid.uuid4()),
        "userId": order.user_id,
        "items": order.items,
        "shipping": order.shipping,
        "total": order.total,
        "status": "Processing",
        "created_at": datetime.datetime.utcnow()
    }
    
    # 2. Save it to the Orders collection
    await db.Orders.insert_one(order_data)
    
    # 3. Empty their database cart so they can start shopping again
    await db.Carts.update_one(
        {"user_id": order.user_id},
        {"$set": {"items": []}}
    )
    
    return {"status": "success", "order_id": order_data["order_id"]}