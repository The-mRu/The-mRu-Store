# backend/api/orders.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
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
        "id": order_id,        # FIXED: was "order_id", real schema uses "id"
        "userId": user_id
    }, {"_id": 0, "status": 1, "orderedAt": 1})

    if not order:
        raise HTTPException(status_code=404, detail="Order not found or does not belong to this account.")

    return {"valid": True, "order_id": order_id, "status": order.get("status", "unknown")}


@router.get("/user/{user_id}")
async def get_user_orders(user_id: str):
    orders = await db.Orders.find({"userId": user_id}, {"_id": 0}).to_list(length=100)
    if not orders:
        raise HTTPException(status_code=404, detail="No orders found for this user")
    return orders


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

    order_seq = await db.Orders.count_documents({}) + 1
    order_id = f"ord_{order_seq:04d}"
    order_number = f"ORD-2026-{order_seq:05d}"
    total_amount = order.subtotal - order.discount + order.shipping_fee

    payment_id = f"pay_{order_seq:05d}"
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
        "orderNumber": order_number,
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

    # backend/api/orders.py — replace the current cart-clear block
    cart = await db.Carts.find_one({"userId": order.user_id})
    if cart:
        await db.CartItems.delete_many({"cartId": cart["id"]})
        await db.Carts.update_one(
            {"id": cart["id"]},
            {"$set": {"totalAmount": 0.0, "updatedAt": datetime.datetime.utcnow()}}
        )

    return {"status": "success", "order_id": order_id, "orderNumber": order_number}



# @router.post("/place")
# async def place_order(order: OrderRequest):
#     """Places a new order, creates the payment record, and clears the user's cart."""
#     address = await db.Addresses.find_one({"id": order.address_id, "userId": order.user_id})
#     if not address:
#         raise HTTPException(status_code=404, detail="Address not found or does not belong to this user.")

#     order_seq = await db.Orders.count_documents({}) + 1
#     order_id = f"ord_{order_seq:04d}"
#     order_number = f"ORD-2026-{order_seq:05d}"
#     total_amount = order.subtotal - order.discount + order.shipping_fee

#     payment_id = f"pay_{order_seq:05d}"
#     payment_data = {
#         "id": payment_id,
#         "orderId": order_id,
#         "paymentMethod": order.payment_method,
#         "transactionId": f"TXN-{uuid.uuid4().hex[:12].upper()}",
#         "amount": total_amount,
#         "currency": "USD",
#         "status": "completed",
#         "paidAt": datetime.datetime.utcnow(),
#     }
#     await db.Payments.insert_one(payment_data)

#     order_data = {
#         "id": order_id,
#         "orderNumber": order_number,
#         "userId": order.user_id,
#         "addressId": order.address_id,
#         "paymentId": payment_id,
#         "items": order.items,
#         "subtotal": order.subtotal,
#         "discount": order.discount,
#         "shippingFee": order.shipping_fee,
#         "totalAmount": total_amount,
#         "status": "Processing",
#         "paymentStatus": "paid",
#         "orderedAt": datetime.datetime.utcnow(),
#         "deliveredAt": None,
#     }
#     await db.Orders.insert_one(order_data)

#     await db.Carts.update_one(
#         {"userId": order.user_id},
#         {"$set": {"items": []}}
#     )

#     return {"status": "success", "order_id": order_id, "orderNumber": order_number}