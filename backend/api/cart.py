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


# backend/api/cart.py
from fastapi import APIRouter, HTTPException, Query
from backend.db.database import db
import uuid
from datetime import datetime, UTC

router = APIRouter()

@router.post("/manage")
@router.get("/manage")
async def manage_cart(
    user_id: str = Query(...),
    action: str = Query(...),
    product_id: str = Query(None),
    quantity: int = Query(1)
):
# @router.post("/manage")
# async def manage_cart(
#     user_id: str = Query(...),
#     action: str = Query(..., description="add | view | update | checkout"),
#     product_id: str = Query(None),
#     quantity: int = Query(1)
# ):
    """Single endpoint for all cart operations."""
    
    # --- VIEW CART ---
    if action == "view":
        cart = await db.Carts.find_one({"userId": user_id})
        if not cart:
            return {"items": [], "total": 0, "message": "Your cart is empty."}

        items = await db.CartItems.find({"cartId": cart["id"]}).to_list(50)

        if not items:
            return {"items": [], "total": 0, "message": "Your cart is empty."}

        # Enrich with product details
        product_ids = [item["productId"] for item in items]
        products = await db.Products.find(
            {"id": {"$in": product_ids}},
            {"_id": 0, "id": 1, "name": 1, "price": 1, "thumbnail": 1, "stock": 1}
        ).to_list(len(product_ids))
        product_map = {p["id"]: p for p in products}

        cart_items = []
        total = 0
        for item in items:
            product = product_map.get(item["productId"], {})
            subtotal = item["quantity"] * item["unitPrice"]
            total += subtotal
            cart_items.append({
                "product_id": item["productId"],
                "name": product.get("name", "Unknown"),
                "price": item["unitPrice"],
                "quantity": item["quantity"],
                "subtotal": round(subtotal, 2),
                "thumbnail": product.get("thumbnail"),
                "in_stock": product.get("stock", 0) > 0
            })

        return {"items": cart_items, "total": round(total, 2), "item_count": len(cart_items)}

    # --- ADD TO CART ---
    elif action == "add":
        if not product_id:
            raise HTTPException(status_code=400, detail="product_id required for 'add'")

        product = await db.Products.find_one({"id": product_id, "status": "active"})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Get or create cart
        cart = await db.Carts.find_one({"userId": user_id})
        if not cart:
            cart_id = f"cart_{uuid.uuid4().hex[:8]}"
            await db.Carts.insert_one({
                "id": cart_id,
                "userId": user_id,
                "totalAmount": 0,
                "createdAt": datetime.now(UTC),
                "updatedAt": datetime.now(UTC)
            })
            cart = {"id": cart_id}

        # Check if product already in cart
        existing = await db.CartItems.find_one({"cartId": cart["id"], "productId": product_id})
        if existing:
            new_qty = existing["quantity"] + quantity
            if new_qty > product.get("stock", 0):
                raise HTTPException(status_code=400, detail=f"Only {product['stock']} in stock. You already have {existing['quantity']}.")
            await db.CartItems.update_one(
                {"_id": existing["_id"]},
                {"$set": {"quantity": new_qty, "updatedAt": datetime.now(UTC)}}
            )
        else:
            await db.CartItems.insert_one({
                "cartId": cart["id"],
                "productId": product_id,
                "name": product["name"],
                "quantity": quantity,
                "unitPrice": product["price"],
                "createdAt": datetime.now(UTC),
                "updatedAt": datetime.now(UTC)
            })

        # Update cart total
        items = await db.CartItems.find({"cartId": cart["id"]}).to_list(50)
        total = sum(item["quantity"] * item["unitPrice"] for item in items)
        await db.Carts.update_one(
            {"id": cart["id"]},
            {"$set": {"totalAmount": total, "updatedAt": datetime.now(UTC)}}
        )

        return {"status": "added", "product": product["name"], "quantity": quantity}

    # --- UPDATE QUANTITY ---
    elif action == "update":
        if not product_id:
            raise HTTPException(status_code=400, detail="product_id required for 'update'")

        cart = await db.Carts.find_one({"userId": user_id})
        if not cart:
            raise HTTPException(status_code=404, detail="Cart is empty")

        if quantity == 0:
            # Remove item
            await db.CartItems.delete_one({"cartId": cart["id"], "productId": product_id})
        else:
            # Update quantity
            product = await db.Products.find_one({"id": product_id})
            if quantity > product.get("stock", 0):
                raise HTTPException(status_code=400, detail=f"Only {product['stock']} in stock.")
            await db.CartItems.update_one(
                {"cartId": cart["id"], "productId": product_id},
                {"$set": {"quantity": quantity, "updatedAt": datetime.now(UTC)}}
            )

        # Recalculate total
        items = await db.CartItems.find({"cartId": cart["id"]}).to_list(50)
        total = sum(item["quantity"] * item["unitPrice"] for item in items)
        await db.Carts.update_one(
            {"id": cart["id"]},
            {"$set": {"totalAmount": total, "updatedAt": datetime.now(UTC)}}
        )

        return {"status": "updated" if quantity > 0 else "removed", "cart_total": round(total, 2)}

    # --- CHECKOUT ---
    # elif action == "checkout":
    #     cart = await db.Carts.find_one({"userId": user_id})
    #     if not cart:
    #         raise HTTPException(status_code=404, detail="Cart is empty")

    #     items = await db.CartItems.find({"cartId": cart["id"]}).to_list(50)
    #     if not items:
    #         raise HTTPException(status_code=400, detail="Cart is empty")

    #     # Validate stock for all items
    #     for item in items:
    #         product = await db.Products.find_one({"id": item["productId"]})
    #         if not product or product.get("stock", 0) < item["quantity"]:
    #             raise HTTPException(
    #                 status_code=400,
    #                 detail=f"Insufficient stock for {item.get('name', item['productId'])}"
    #             )

    #     # Create order
    #     order_id = f"ord_{uuid.uuid4().hex[:8]}"
    #     subtotal = sum(item["quantity"] * item["unitPrice"] for item in items)

    #     order_data = {
    #         "id": order_id,
    #         "userId": user_id,
    #         "items": [{"productId": i["productId"], "name": i["name"], "quantity": i["quantity"], "price": i["unitPrice"]} for i in items],
    #         "subtotal": subtotal,
    #         "discount": 0,
    #         "shippingFee": 0,
    #         "totalAmount": subtotal,
    #         "status": "Processing",
    #         "paymentStatus": "paid",
    #         "orderedAt": datetime.now(UTC),
    #         "deliveredAt": None,
    #     }
    #     await db.Orders.insert_one(order_data)

    #     # Create OrderItems and deduct stock
    #     for item in items:
    #         await db.OrderItems.insert_one({
    #             "orderId": order_id,
    #             "productId": item["productId"],
    #             "name": item["name"],
    #             "quantity": item["quantity"],
    #             "unitPrice": item["unitPrice"],
    #             "totalPrice": item["quantity"] * item["unitPrice"],
    #             "createdAt": datetime.now(UTC)
    #         })
    #         await db.Products.update_one(
    #             {"id": item["productId"]},
    #             {"$inc": {"stock": -item["quantity"]}}
    #         )

    #     # Clear cart
    #     await db.CartItems.delete_many({"cartId": cart["id"]})
    #     await db.Carts.update_one(
    #         {"id": cart["id"]},
    #         {"$set": {"totalAmount": 0, "updatedAt": datetime.now(UTC)}}
    #     )

    #     return {
    #         "status": "success",
    #         "order_id": order_id,
    #         "total": round(subtotal, 2),
    #         "item_count": len(items)
    #     }
    elif action == "checkout":
        raise HTTPException(
            status_code=400,
            detail="Chatbot checkout is disabled. Please direct the user to the /checkout/ page."
    )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")