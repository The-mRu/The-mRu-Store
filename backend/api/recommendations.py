# backend/api/recommendations.py
from fastapi import APIRouter, Query
from typing import Optional, List
from backend.db.database import db
from backend.api.search import search_products_core

router = APIRouter()


@router.get("/")
async def recommend_products(
    need: str = Query(...),
    category: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
    min_rating: Optional[float] = Query(None),
):
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


@router.get("/compare")
async def compare_products(product_ids: List[str] = Query(...)):
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


@router.get("/similar/{product_id}")
async def get_similar_products(product_id: str):
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