# backend/api/orders.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

import re
from backend.db.database import db
import uuid
import datetime

router = APIRouter()

# --- PYDANTIC MODELS ---
class OrderRequest(BaseModel):
    user_id: str
    items: List[Dict[str, Any]]
    address_id: Optional[str] = None
    shipping_address: Optional[Dict[str, str]] = None
    payment_method: str
    subtotal: float
    discount: float = 0.0
    shipping_fee: float = 0.0


@router.get("/")
async def get_all_orders():
    """Retrieve all orders (Admin only ideally)."""
    orders = await db.Orders.find({}, {"_id": 0}).to_list(length=100)
    return orders


@router.get("/{order_id}")
async def verify_order_for_ai(order_id: str, user_id: str):
    order = await db.Orders.find_one({
        "id": {"$regex": f"^{re.escape(order_id)}$", "$options": "i"},
        "userId": user_id
    }, {"_id": 0, "status": 1, "orderedAt": 1, "id": 1})

    if not order:
        raise HTTPException(status_code=404, detail="Order not found or does not belong to this account.")

    return {"valid": True, "order_id": order.get("id"), "status": order.get("status", "unknown")}


@router.get("/user/{user_id}")
async def get_user_orders(user_id: str, limit: int = 5):
    total_count = await db.Orders.count_documents({"userId": user_id})
    if total_count == 0:
        raise HTTPException(status_code=404, detail="No orders found for this user")

    orders = await db.Orders.find(
        {"userId": user_id}, {"_id": 0}
    ).sort("orderedAt", -1).limit(limit).to_list(limit)

    cleaned_orders = []
    for o in orders:
        cleaned_orders.append({
            "order_id": o.get("id"),
            "status": o.get("status"),
            "total_amount": o.get("totalAmount"),
            "ordered_at": o.get("orderedAt"),
        })

    return {
        "orders": cleaned_orders,
        "shown": len(cleaned_orders),
        "total_orders": total_count,
        "has_more": total_count > len(cleaned_orders)
    }


@router.get("/{order_id}/items")
async def get_order_items(order_id: str, user_id: str):
    order = await db.Orders.find_one(
        {"id": {"$regex": f"^{re.escape(order_id)}$", "$options": "i"}, "userId": user_id},
        {"_id": 0, "id": 1, "items": 1}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or does not belong to this account.")

    real_order_id = order["id"]

    # Try the proper OrderItems collection first (current, correct path)
    items = await db.OrderItems.find({"orderId": real_order_id}, {"_id": 0}).to_list(length=100)

    if items:
        product_ids = [item["productId"] for item in items]
        products = await db.Products.find(
            {"id": {"$in": product_ids}}, {"_id": 0, "id": 1, "name": 1, "thumbnail": 1, "status": 1}
        ).to_list(len(product_ids))
        product_lookup = {p["id"]: p for p in products}

        enriched_items = []
        for item in items:
            product = product_lookup.get(item["productId"])
            enriched_items.append({
                "product_id": item["productId"],
                "name": product["name"] if product else "Product no longer available",
                "thumbnail": product.get("thumbnail") if product else None,
                "quantity": item["quantity"],
                "unit_price_paid": item["unitPrice"],
                "total_price": item["totalPrice"],
                "currently_available": bool(product and product.get("status") == "active"),
            })
        return {"order_id": real_order_id, "items": enriched_items}

    # Fallback: legacy orders with embedded items array
    legacy_items = order.get("items", [])
    if not legacy_items:
        return {"order_id": real_order_id, "items": []}

    enriched_items = []
    for item in legacy_items:
        enriched_items.append({
            "product_id": item.get("productId"),
            "name": item.get("name", "Unknown item (legacy order)"),
            "thumbnail": None,
            "quantity": item.get("quantity", 1),
            "unit_price_paid": item.get("price", 0),
            "total_price": item.get("price", 0) * item.get("quantity", 1),
            "currently_available": None,
        })
    return {"order_id": real_order_id, "items": enriched_items}

@router.post("/place")
async def place_order(order: OrderRequest):
    """Places a new order, creates the payment record, and clears the user's cart."""
    if order.address_id:
        address = await db.Addresses.find_one({"id": order.address_id, "userId": order.user_id})
        if not address:
            raise HTTPException(status_code=404, detail="Address not found or does not belong to this user.")
        address_id = order.address_id
    elif order.shipping_address:
        address_id = f"addr_{uuid.uuid4().hex[:8]}"
        await db.Addresses.insert_one({
            "id": address_id,
            "userId": order.user_id,
            "fullName": order.shipping_address.get("fullName", ""),
            "phone": order.shipping_address.get("phone", ""),
            "country": "Bangladesh",
            "city": order.shipping_address.get("division", ""),
            "area": "",
            "street": order.shipping_address.get("address", ""),
            "postalCode": "",
            "isDefault": False,
            "createdAt": datetime.datetime.utcnow(),
        })
    else:
        raise HTTPException(status_code=400, detail="Either address_id or shipping_address is required.")

    # =========================================================================
    # STOCK VALIDATION & DEDUCTION — check BEFORE creating the order
    # =========================================================================
    for item in order.items:
        product_id = item.get("productId")
        quantity = item.get("quantity", 1)
        if not product_id:
            continue

        # Atomically decrement stock — only succeeds if enough stock exists
        result = await db.Products.update_one(
            {"id": product_id, "stock": {"$gte": quantity}},
            {"$inc": {"stock": -quantity}}
        )
        if result.modified_count == 0:
            # Either product doesn't exist or insufficient stock
            product = await db.Products.find_one({"id": product_id}, {"name": 1, "stock": 1})
            available = product["stock"] if product else 0
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.get('name', product_id)}'. Requested: {quantity}, Available: {available}"
            )
    # =========================================================================

    order_id = f"ord_{uuid.uuid4().hex[:8]}"
    total_amount = order.subtotal - order.discount + order.shipping_fee

    payment_id = f"pay_{uuid.uuid4().hex[:8]}"
    payment_data = {
        "id": payment_id,
        "orderId": order_id,
        "paymentMethod": order.payment_method,
        "transactionId": f"TXN-{uuid.uuid4().hex[:12].upper()}",
        "amount": total_amount,
        "currency": "USD",
        "status": "completed",
        "paidAt": datetime.datetime.utcnow(),
    }
    await db.Payments.insert_one(payment_data)

    order_data = {
        "id": order_id,
        "userId": order.user_id,
        "addressId": address_id,
        "paymentId": payment_id,
        "items": order.items,
        "subtotal": order.subtotal,
        "discount": order.discount,
        "shippingFee": order.shipping_fee,
        "totalAmount": total_amount,
        "status": "Processing",
        "paymentStatus": "paid",
        "orderedAt": datetime.datetime.utcnow(),
        "deliveredAt": None,
    }
    await db.Orders.insert_one(order_data)

    # =========================================================================
    # CREATE OrderItems — required for Top Products analytics
    # =========================================================================
    now = datetime.datetime.utcnow()
    for item in order.items:
        await db.OrderItems.insert_one({
            "orderId": order_id,
            "productId": item.get("productId"),
            "name": item.get("name", ""),
            "quantity": item.get("quantity", 1),
            "unitPrice": item.get("price", 0),
            "totalPrice": item.get("price", 0) * item.get("quantity", 1),
            "createdAt": now
        })
    # =========================================================================

    cart = await db.Carts.find_one({"userId": order.user_id})
    if cart:
        await db.CartItems.delete_many({"cartId": cart["id"]})
        await db.Carts.update_one(
            {"id": cart["id"]},
            {"$set": {"totalAmount": 0.0, "updatedAt": datetime.datetime.utcnow()}}
        )

    return {"status": "success", "order_id": order_id}