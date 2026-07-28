import datetime
import uuid

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

async def sync_cart(request: CartSyncRequest):
    """Saves the user's cart to MongoDB, overwriting the old one."""
    cart = await db.Carts.find_one({"userId": request.user_id})
    if cart:
        cart_id = cart["id"]
    else:
        cart_id = str(uuid.uuid4())

    # Look up real, current prices for every product in the cart —
    # never trust a client-supplied price (CartItem doesn't even have one, correctly)
    product_ids = [item.productId for item in request.items]
    products = await db.Products.find(
        {"id": {"$in": product_ids}}, {"id": 1, "price": 1, "_id": 0}
    ).to_list(length=len(product_ids))
    price_lookup = {p["id"]: p.get("price", 0) for p in products}

    cart_item_docs = []
    total_amount = 0.0
    for item in request.items:
        unit_price = price_lookup.get(item.productId, 0)
        line_total = unit_price * item.quantity
        total_amount += line_total
        cart_item_docs.append({
            "id": f"c_item_{uuid.uuid4().hex[:8]}",
            "cartId": cart_id,
            "productId": item.productId,
            "quantity": item.quantity,
            "unitPrice": unit_price,
            "totalPrice": line_total,
            "createdAt": datetime.datetime.utcnow(),
        })

    if cart:
        await db.Carts.update_one(
            {"userId": request.user_id},
            {"$set": {"totalAmount": total_amount, "updatedAt": datetime.datetime.utcnow()}}
        )
    else:
        await db.Carts.insert_one({
            "id": cart_id,
            "userId": request.user_id,
            "totalAmount": total_amount,
            "createdAt": datetime.datetime.utcnow(),
            "updatedAt": datetime.datetime.utcnow(),
        })

    await db.CartItems.delete_many({"cartId": cart_id})
    if cart_item_docs:
        await db.CartItems.insert_many(cart_item_docs)

    return {"status": "success"}


@router.get("/{user_id}")
async def get_cart(user_id: str):
    """Fetches the user's saved cart, including its line items, from MongoDB."""
    cart = await db.Carts.find_one({"userId": user_id}, {"_id": 0})
    if not cart:
        return {"userId": user_id, "items": [], "totalAmount": 0.0}

    items = await db.CartItems.find({"cartId": cart["id"]}, {"_id": 0}).to_list(length=100)
    cart["items"] = items
    return cart