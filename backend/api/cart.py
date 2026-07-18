from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from backend.db.database import db

router = APIRouter()

class CartItem(BaseModel):
    productId: str
    quantity: int

class CartSyncRequest(BaseModel):
    user_id: str
    items: List[CartItem]

@router.post("/sync")
async def sync_cart(request: CartSyncRequest):
    """Saves the user's cart to MongoDB, overwriting the old one."""
    cart_data = {
        "user_id": request.user_id,
        "items": [item.dict() for item in request.items]
    }
    # upsert=True means if the user doesn't have a cart, create one. If they do, update it.
    await db.Carts.update_one(
        {"user_id": request.user_id},
        {"$set": cart_data},
        upsert=True
    )
    return {"status": "success"}

@router.get("/{user_id}")
async def get_cart(user_id: str):
    """Fetches the user's saved cart from MongoDB."""
    cart = await db.Carts.find_one({"user_id": user_id}, {"_id": 0})
    return cart if cart else {"user_id": user_id, "items": []}