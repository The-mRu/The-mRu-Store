# backend/api/recommendations.py
from fastapi import APIRouter, Query
from typing import Optional, List
import json
from datetime import datetime
from backend.db.database import db
from backend.api.search import search_products_core

router = APIRouter()


# =============================================================================
# PREFERENCES — store & retrieve user preferences
# =============================================================================

@router.post("/preferences/{user_id}")
async def remember_preference(
    user_id: str,
    brand: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    budget_max: Optional[float] = Query(None),
):
    """Store a stated user preference for future personalization."""
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
        ops["$addToSet"] = push

    await db.UserPreferences.update_one({"userId": user_id}, ops, upsert=True)
    return {"status": "saved"}


@router.get("/preferences/{user_id}")
async def get_preferences(user_id: str):
    """Retrieve stored preferences for a user."""
    prefs = await db.UserPreferences.find_one({"userId": user_id}, {"_id": 0})
    return prefs or {
        "userId": user_id,
        "preferredBrands": [],
        "preferredCategories": [],
        "budgetMax": None,
    }


# =============================================================================
# PERSONALIZED RECOMMENDATIONS — combines preferences + orders + wishlist
# =============================================================================

@router.get("/personalized/{user_id}")
async def get_personalized_recommendations(user_id: str):
    """Recommend products based on stored preferences, purchase history, and wishlist."""
    prefs = await db.UserPreferences.find_one({"userId": user_id}) or {}

    # Signal from purchase history
    past_orders = await db.Orders.find({"userId": user_id}).to_list(50)
    order_ids = [o.get("id") for o in past_orders]
    order_items = await db.OrderItems.find(
        {"orderId": {"$in": order_ids}}, {"productId": 1}
    ).to_list(200) if order_ids else []
    purchased_product_ids = list(set(i["productId"] for i in order_items))
    purchased_products = await db.Products.find(
        {"id": {"$in": purchased_product_ids}}, {"brandId": 1, "categoryId": 1}
    ).to_list(len(purchased_product_ids)) if purchased_product_ids else []

    # Signal from wishlist
    wishlist = await db.Wishlists.find_one({"userId": user_id})
    wishlist_product_ids = []
    if wishlist:
        wishlist_items = await db.WishlistItems.find({"wishlistId": wishlist["id"]}).to_list(50)
        wishlist_product_ids = [item["productId"] for item in wishlist_items]
    wishlist_products = await db.Products.find(
        {"id": {"$in": wishlist_product_ids}}, {"brandId": 1, "categoryId": 1}
    ).to_list(len(wishlist_product_ids)) if wishlist_product_ids else []

    # Merge signals: explicit > purchase history > wishlist
    brand_ids = set(prefs.get("preferredBrands", []))
    brand_ids |= {p["brandId"] for p in purchased_products if p.get("brandId")}
    brand_ids |= {p["brandId"] for p in wishlist_products if p.get("brandId")}

    category_ids = {p["categoryId"] for p in purchased_products if p.get("categoryId")}
    category_ids |= {p["categoryId"] for p in wishlist_products if p.get("categoryId")}

    # Build query
    query = {"status": "active"}
    if brand_ids:
        query["brandId"] = {"$in": list(brand_ids)}
    if prefs.get("budgetMax"):
        query["price"] = {"$lte": prefs["budgetMax"]}

    results = await db.Products.find(query, {"_id": 0, "embedding": 0}).limit(10).to_list(10)

    # Relax to category-only if brand+budget was too narrow
    if not results and category_ids:
        results = await db.Products.find(
            {"status": "active", "categoryId": {"$in": list(category_ids)}},
            {"_id": 0, "embedding": 0}
        ).limit(10).to_list(10)

    return {
        "recommendations": results[:5],
        "based_on": {
            "stated_preferences": bool(prefs.get("preferredBrands") or prefs.get("budgetMax")),
            "brands_considered": list(brand_ids),
            "from_purchase_history": len(purchased_products) > 0,
            "from_wishlist": len(wishlist_products) > 0,
        }
    }


# =============================================================================
# RECENTLY DISCUSSED — products from past chat conversations
# =============================================================================

@router.get("/recent-context/{user_id}")
async def get_recently_discussed(user_id: str, hint: Optional[str] = Query(None)):
    """Find products the chatbot previously showed this user in past conversations."""
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
                except (json.JSONDecodeError, TypeError):
                    continue

    if not mentioned_product_ids:
        return {"products": [], "note": "No recently discussed products found."}

    query = {"id": {"$in": list(mentioned_product_ids)}}
    if hint:
        query["$or"] = [
            {"name": {"$regex": hint, "$options": "i"}},
            {"category": {"$regex": hint, "$options": "i"}},
        ]

    products = await db.Products.find(query, {"_id": 0, "embedding": 0}).limit(5).to_list(5)
    return {
        "products": products,
        "note": "Based on products discussed in recent chat conversations."
    }


# =============================================================================
# NEED-BASED RECOMMENDATIONS — "phone for gaming", "laptop under $700"
# =============================================================================

@router.get("/")
async def recommend_products(
    need: str = Query(..., description="What the user needs, e.g. 'gaming', 'university'"),
    category: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
    min_rating: Optional[float] = Query(None),
):
    """Recommend products based on a described need, re-ranked by stock/rating signals."""
    search_result = await search_products_core(q=need, category=category, max_price=max_price)
    products = search_result["products"]

    if min_rating:
        products = [p for p in products if p.get("rating", 0) >= min_rating]

    def recommendation_score(p):
        stock_bonus = 0.1 if p.get("stock", 0) > 0 else -0.5
        rating_bonus = (p.get("rating", 0) / 5.0) * 0.3
        review_confidence = min(p.get("totalReviews", 0) / 20, 1.0) * 0.1
        return stock_bonus + rating_bonus + review_confidence

    products.sort(key=recommendation_score, reverse=True)
    return {"recommendations": products[:5], "relaxed": search_result["relaxed"]}


# =============================================================================
# COMPARE — side-by-side product comparison
# =============================================================================

@router.get("/compare")
async def compare_products(product_ids: List[str] = Query(...)):
    """Compare 2-3 products side-by-side."""
    if len(product_ids) < 2 or len(product_ids) > 3:
        from fastapi import HTTPException
        raise HTTPException(400, "Provide 2 or 3 product IDs.")

    products = await db.Products.find(
        {"id": {"$in": product_ids}}, {"_id": 0, "embedding": 0}
    ).to_list(len(product_ids))

    comparison = []
    for p in products:
        recent_reviews = await db.Reviews.find(
            {"productId": p["id"]}, {"_id": 0, "comment": 1, "rating": 1}
        ).sort("createdAt", -1).limit(3).to_list(3)

        comparison.append({
            "name": p["name"],
            "price": p["price"],
            "discountPrice": p.get("discountPrice"),
            "rating": p.get("rating", 0.0),
            "totalReviews": p.get("totalReviews", 0),
            "warranty": p.get("warranty", "No Warranty"),
            "stock": p.get("stock", 0),
            "in_stock": p.get("stock", 0) > 0,
            "recent_review_snippets": [r["comment"] for r in recent_reviews] if recent_reviews else ["No reviews yet"],
        })

    return {"comparison": comparison}


# =============================================================================
# SIMILAR PRODUCTS — same category, similar price, same brand preferred
# =============================================================================

@router.get("/similar/{product_id}")
async def get_similar_products(product_id: str):
    """Find products similar to the given one."""
    base = await db.Products.find_one({"id": product_id})
    if not base:
        return {"similar": []}

    price = base.get("price", 0)
    price_range = {"$gte": price * 0.7, "$lte": price * 1.3}

    query = {
        "id": {"$ne": product_id},
        "categoryId": base.get("categoryId"),
        "price": price_range,
        "status": "active"
    }

    same_brand = await db.Products.find(
        {**query, "brandId": base.get("brandId")}, {"_id": 0, "embedding": 0}
    ).to_list(10) if base.get("brandId") else []

    others = await db.Products.find(query, {"_id": 0, "embedding": 0}).to_list(10)

    combined = same_brand + [p for p in others if p["id"] not in {s["id"] for s in same_brand}]
    return {"similar": combined[:5]}