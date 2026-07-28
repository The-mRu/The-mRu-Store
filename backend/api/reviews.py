# backend/api/reviews.py
from fastapi import APIRouter, HTTPException
from backend.db.database import db

router = APIRouter()

@router.get("/product/{product_id}")
async def get_reviews_for_product(product_id: str):
    reviews = await db.Reviews.find({"productId": product_id}, {"_id": 0}).to_list(length=100)
    if not reviews:
        raise HTTPException(status_code=404, detail="No reviews found for this product")
    return reviews

@router.get("/")
async def get_all_reviews():
    reviews = await db.Reviews.find({}, {"_id": 0}).to_list(length=100)
    return reviews

@router.get("/summary/{product_id}")
async def get_review_summary(product_id: str):
    """AI-facing endpoint — returns rating summary + recent reviews, never 404s on empty (a product can genuinely have zero reviews)."""
    product = await db.Products.find_one(
        {"id": product_id}, {"_id": 0, "name": 1, "rating": 1, "totalReviews": 1}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    reviews = await db.Reviews.find(
        {"productId": product_id}, {"_id": 0, "rating": 1, "comment": 1, "createdAt": 1}
    ).sort("createdAt", -1).limit(10).to_list(10)

    if not reviews:
        return {
            "product_name": product["name"],
            "average_rating": 0.0,
            "total_reviews": 0,
            "recent_reviews": [],
            "message": "This product has no reviews yet."
        }

    return {
        "product_name": product["name"],
        "average_rating": product.get("rating", 0.0),
        "total_reviews": product.get("totalReviews", len(reviews)),
        "recent_reviews": [{"rating": r["rating"], "comment": r["comment"]} for r in reviews]
    }