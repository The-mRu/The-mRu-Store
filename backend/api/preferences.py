# backend/api/preferences.py
from fastapi import APIRouter
from backend.db.database import db
from datetime import datetime

router = APIRouter()

@router.post("/{user_id}")
async def update_preference(user_id: str, brand: str = None, category: str = None, budget_max: float = None):
    update = {"updatedAt": datetime.utcnow()}
    push = {}
    if brand:
        push["preferredBrands"] = brand
    if category:
        push["preferredCategories"] = category
    if budget_max is not None:
        update["budgetMax"] = budget_max

    ops = {"$set": update}
    if push:
        ops["$addToSet"] = push   # avoids duplicate brand/category entries

    await db.UserPreferences.update_one({"userId": user_id}, ops, upsert=True)
    return {"status": "saved"}


@router.get("/{user_id}")
async def get_preferences(user_id: str):
    prefs = await db.UserPreferences.find_one({"userId": user_id}, {"_id": 0})
    return prefs or {"userId": user_id, "preferredBrands": [], "preferredCategories": [], "budgetMax": None}

@router.get("/personalized/{user_id}")
async def get_personalized_recommendations(user_id: str):
    prefs = await db.UserPreferences.find_one({"userId": user_id}) or {}

    # Infer signal from real purchase history — which brands/categories has this user actually bought?
    past_orders = await db.Orders.find({"userId": user_id}, {"items": 1}).to_list(50)
    order_items = await db.OrderItems.find(
        {"orderId": {"$in": [o.get("id") for o in past_orders]}}, {"productId": 1}
    ).to_list(200)
    purchased_product_ids = [i["productId"] for i in order_items]
    purchased_products = await db.Products.find(
        {"id": {"$in": purchased_product_ids}}, {"brandId": 1, "categoryId": 1}
    ).to_list(200)

    wishlist_items = await db.Wishlist.find({"userId": user_id}, {"productId": 1}).to_list(50)
    wishlist_products = await db.Products.find(
        {"id": {"$in": [w["productId"] for w in wishlist_items]}}, {"brandId": 1, "categoryId": 1}
    ).to_list(50)

    # Merge signals: explicit preference > purchase history > wishlist
    brand_ids = set(prefs.get("preferredBrands", []))
    brand_ids |= {p["brandId"] for p in purchased_products if p.get("brandId")}
    brand_ids |= {p["brandId"] for p in wishlist_products if p.get("brandId")}

    category_ids = {p["categoryId"] for p in purchased_products if p.get("categoryId")}
    category_ids |= {p["categoryId"] for p in wishlist_products if p.get("categoryId")}

    query = {"status": "active"}
    if brand_ids:
        query["brandId"] = {"$in": list(brand_ids)}
    if prefs.get("budgetMax"):
        query["price"] = {"$lte": prefs["budgetMax"]}

    results = await db.Products.find(query, {"_id": 0, "embedding": 0}).limit(10).to_list(10)

    if not results and category_ids:
        # relax to category-only if brand+budget was too narrow
        results = await db.Products.find(
            {"status": "active", "categoryId": {"$in": list(category_ids)}}, {"_id": 0, "embedding": 0}
        ).limit(10).to_list(10)

    return {"recommendations": results[:5], "based_on": {
        "stated_preferences": bool(prefs),
        "brands_considered": list(brand_ids),
        "from_purchase_history": len(purchased_products) > 0,
        "from_wishlist": len(wishlist_products) > 0
    }}
    
    
@router.get("/recent-context/{user_id}")
async def get_recently_discussed(user_id: str, hint: str = None):
    sessions = await db.ChatSessions.find(
        {"userId": user_id}
    ).sort("updatedAt", -1).limit(5).to_list(5)

    mentioned_product_ids = set()
    for session in sessions:
        for msg in session.get("messages", []):
            if msg.get("role") == "tool":
                try:
                    content = json.loads(msg.get("content", "{}"))
                    products = content.get("products") or content.get("recommendations") or []
                    for p in products:
                        if isinstance(p, dict) and p.get("id"):
                            mentioned_product_ids.add(p["id"])
                except Exception:
                    continue

    if not mentioned_product_ids:
        return {"products": []}

    query = {"id": {"$in": list(mentioned_product_ids)}}
    if hint:
        query["$or"] = [
            {"name": {"$regex": hint, "$options": "i"}},
            {"category": {"$regex": hint, "$options": "i"}}
        ]

    products = await db.Products.find(query, {"_id": 0, "embedding": 0}).limit(5).to_list(5)
    return {"products": products}