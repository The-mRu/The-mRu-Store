# scripts/fixing.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from bson.objectid import ObjectId

async def backfill():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.amazon_clone_db
    
    # Find orders with items but no OrderItems
    pipeline = [
        {
            "$lookup": {
                "from": "OrderItems",
                "localField": "id",
                "foreignField": "orderId",
                "as": "orderItems"
            }
        },
        {"$match": {"orderItems": {"$size": 0}, "items": {"$ne": None, "$not": {"$size": 0}}}},
        {"$project": {"_id": 0, "id": 1, "items": 1, "orderedAt": 1}}
    ]
    
    orders = await db.Orders.aggregate(pipeline).to_list(length=1000)
    print(f"Found {len(orders)} orders to backfill")
    count = 0
    
    for order in orders:
        embedded_items = order.get("items", [])
        for item in embedded_items:
            # Resolve productId: it might be an ObjectId, need to find the real product id
            raw_pid = item.get("productId")
            if isinstance(raw_pid, ObjectId):
                product = await db.Products.find_one({"_id": raw_pid}, {"id": 1, "name": 1})
                product_id = product["id"] if product else str(raw_pid)
                product_name = product["name"] if product else item.get("name", "Unknown")
            else:
                product_id = str(raw_pid) if raw_pid else None
                product_name = item.get("name", "Unknown")
            
            await db.OrderItems.insert_one({
                "orderId": order["id"],
                "productId": product_id,
                "name": product_name,
                "quantity": item.get("quantity", 1),
                "unitPrice": item.get("price", 0),
                "totalPrice": item.get("price", 0) * item.get("quantity", 1),
                "createdAt": order.get("orderedAt", datetime.utcnow())
            })
            count += 1
    
    print(f"Backfilled {count} OrderItems from {len(orders)} orders.")

asyncio.run(backfill())