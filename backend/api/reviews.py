# backend/api/reviews.py
import os
import re

from datetime import datetime

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI

from backend.db.database import db

load_dotenv()

router = APIRouter()
_openai_client = None


def get_openai_client():
    global _openai_client

    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_ADMIN_KEY")
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="OPENAI_API_KEY is missing. Add it to your environment or .env file."
            )
        _openai_client = AsyncOpenAI(api_key=api_key)

    return _openai_client


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


@router.get("/ai-summary-lookup")
async def get_review_summary_flexible(product_id: str = None, product_name: str = None):
    product = None
    if product_id:
        product = await db.Products.find_one({"id": product_id}, {"_id": 0, "id": 1, "name": 1})

    if not product and product_name:
        matches = await db.Products.find(
            {"name": {"$regex": f"^{re.escape(product_name)}", "$options": "i"}, "status": "active"},
            {"_id": 0, "id": 1, "name": 1, "brand": 1}
        ).to_list(5)

        if len(matches) == 1:
            product = matches[0]
        elif len(matches) > 1:
            # Ambiguous — don't silently guess, tell the caller so it can ask the user
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Multiple products match this name — need more specificity.",
                    "candidates": [{"id": m["id"], "name": m["name"], "brand": m.get("brand")} for m in matches]
                }
            )

    if not product:
        raise HTTPException(status_code=404, detail="Could not find this product by ID or name.")

    real_id = product["id"]
    reviews = await db.Reviews.find(
        {"productId": real_id}, {"_id": 0, "rating": 1, "comment": 1, "createdAt": 1}
    ).sort("createdAt", -1).limit(10).to_list(10)

    if not reviews:
        return {"product_name": product["name"], "average_rating": 0.0, "total_reviews": 0, "recent_reviews": [], "message": "No reviews yet."}

    prod_full = await db.Products.find_one({"id": real_id}, {"rating": 1, "totalReviews": 1})
    return {
        "product_name": product["name"],
        "average_rating": prod_full.get("rating", 0.0),
        "total_reviews": prod_full.get("totalReviews", len(reviews)),
        "recent_reviews": [{"rating": r["rating"], "comment": r["comment"]} for r in reviews]
    }



@router.get("/summary/{product_id}")
async def get_review_summary(product_id: str):
    """
    AI-facing endpoint — returns rating summary + recent reviews.
    Never 404s on zero reviews (a real product can genuinely have none) —
    only 404s if the product itself doesn't exist.
    Strict id-based lookup: with the orchestrator's product_id registry now
    resolving/validating ids before this is ever called, this endpoint no
    longer needs fuzzy name-matching as a fallback.
    """
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




@router.get("/ai-summary/{product_id}")  ### review summary endpoint for product detail page 
async def get_ai_review_summary(product_id: str):
    """
    On-demand AI-generated summary of a product's reviews, weighted toward
    the most recent ones. Not cached — future frontend can call this whenever
    it needs a fresh summary (e.g. product detail page load).
    """
    product = await db.Products.find_one({"id": product_id}, {"_id": 0, "name": 1})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    reviews = await db.Reviews.find(
        {"productId": product_id}, {"rating": 1, "comment": 1, "createdAt": 1}
    ).sort("createdAt", -1).limit(20).to_list(20)

    if not reviews:
        return {"product_name": product["name"], "summary": "This product has no reviews yet."}

    review_text = "\n".join([f"({r['rating']}★) {r['comment']}" for r in reviews])
    prompt = (
        "Summarize these customer reviews in 2-3 sentences. Weight the most recent reviews "
        "(listed first) more heavily, since they reflect the product's current state:\n\n"
        f"{review_text}"
    )

    client = get_openai_client()
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    summary = response.choices[0].message.content

    return {"product_name": product["name"], "summary": summary}