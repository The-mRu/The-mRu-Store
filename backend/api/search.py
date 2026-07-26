# backend/api/search.py
from fastapi import APIRouter, HTTPException, Query
from backend.db.database import db
from sentence_transformers import SentenceTransformer
import math
from pydantic import BaseModel
from typing import Optional
import re
from typing import Optional, List, Dict

router = APIRouter()


print("Loading AI Search Model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


# -------------------------------------------------------
def calculate_similarity(v1, v2):
    """Cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    if magnitude1 * magnitude2 == 0:
        return 0
    return dot_product / (magnitude1 * magnitude2)


def normalize_text(s: str) -> str:
    """Strip everything except letters/digits, lowercased.
    't-shirt', 'tshirt', 't shirt' → 'tshirt'
    """
    return re.sub(r'[^a-z0-9]', '', s.lower())


# -------------------------------------------------------
@router.get("/", description="Omnibox search designed for AI Agents with Smart Filtering & Fallback.")
async def ai_omni_search(
    q: Optional[str] = Query(None, description="General search keyword(s)"),
    brand: Optional[str] = Query(None, description="Strict brand filter"),
    category: Optional[str] = Query(None, description="Strict category filter"),
    min_price: Optional[float] = Query(None, description="Minimum price limit"),
    max_price: Optional[float] = Query(None, description="Maximum price limit")
):
    query = {}
    and_conditions = []

    # 1. Keyword search – FIXED: Handles 'ss', hyphens, and the 'tshirt' edge case
    if q:
        words = []
        for w in q.strip().split():
            if len(w) > 1:
                # 1. Preserve words ending in 'ss' (like 'dress'), otherwise strip plural 's'
                clean_w = w if w.lower().endswith('ss') else re.sub(r'(s|es)$', '', w, flags=re.IGNORECASE)
                
                # 2. Fix the T-Shirt Edge Case
                if clean_w.lower() == "tshirt":
                    clean_w = "t[- ]?shirt"
                else:
                    # 3. Make all other hyphens optional
                    clean_w = clean_w.replace("-", "[- ]?")
                    
                words.append(clean_w)
                
        if words:
            word_conditions = []
            for word in words:
                word_regex = {"$regex": word, "$options": "i"}
                word_conditions.append({
                    "$or": [
                        {"name": word_regex},
                        {"shortDescription": word_regex},
                        {"description": word_regex}
                    ]
                })
            and_conditions.extend(word_conditions)

    # 2. Brand filter
    if brand:
        b = await _resolve_by_tokens(db.Brands, brand)
        if b:
            and_conditions.append({"brandId": b["id"]})
        else:
            and_conditions.append({"name": {"$regex": re.escape(brand.strip()), "$options": "i"}})

    # 3. Category filter — strict tokenized AND logic
    if category:
        c = await _resolve_by_tokens(db.Categories, category)
        if c:
            and_conditions.append({"categoryId": c["id"]})
        else:
            cat_words = [re.sub(r'(s|es)$', '', w, flags=re.IGNORECASE) for w in category.strip().split() if len(w) > 1]
            for word in cat_words:
                and_conditions.append({"$or": [
                    {"name": {"$regex": word, "$options": "i"}},
                    {"description": {"$regex": word, "$options": "i"}}
                ]})

    # 4. Price range
    if min_price is not None or max_price is not None:
        price_query = {}
        if min_price is not None:
            price_query["$gte"] = min_price
        if max_price is not None:
            price_query["$lte"] = max_price
        and_conditions.append({"price": price_query})

    if and_conditions:
        query["$and"] = and_conditions

    products = await db.Products.find(query, {"_id": 0}).to_list(length=100)

    # 5. Semantic fallback
    relaxed = []
    if not products and q:
        products, relaxed = await _semantic_fallback(q, min_price, max_price)

    if not products:
        raise HTTPException(status_code=404, detail="No products found matching these criteria.")

    # 6. UI defaults
    DEFAULT_THUMBNAIL = "/static/images/placeholder.png"
    for product in products:
        product.setdefault("thumbnail", DEFAULT_THUMBNAIL) or None
        if not product.get("thumbnail"):
            product["thumbnail"] = DEFAULT_THUMBNAIL
        product.setdefault("discountPrice", None)
        product.setdefault("rating", 0.0)

    return {"products": products, "relaxed": relaxed} if relaxed else products


# -------------------- Helper functions --------------------
async def _resolve_by_tokens(collection, phrase: str):
    """Try exact match first, then require ALL words to match, not just one."""
    # 1. Exact match attempt
    doc = await collection.find_one({"name": {"$regex": phrase.strip(), "$options": "i"}})
    if doc:
        return doc
        
    # 2. Tokenized AND match (Strict)
    words = [re.sub(r'(s|es)$', '', w, flags=re.IGNORECASE) for w in phrase.strip().split() if len(w) > 1]
    if not words:
        return None
        
    and_conditions = [{"name": {"$regex": word, "$options": "i"}} for word in words]
    return await collection.find_one({"$and": and_conditions})


async def _semantic_fallback(q: str, min_price: Optional[float], max_price: Optional[float]):
    """Embed the query and rank products by meaning, not literal substring match."""
    query_vector = embedding_model.encode(q).tolist()

    price_query = {}
    if min_price is not None:
        price_query["$gte"] = min_price
    if max_price is not None:
        price_query["$lte"] = max_price
    mongo_filter = {"price": price_query} if price_query else {}

    cursor = db.Products.find(mongo_filter, {"_id": 0})
    scored = []
    async for doc in cursor:
        vec = doc.get("embedding")
        if not vec:
            continue
        score = calculate_similarity(query_vector, vec)
        if score >= 0.40:         
            doc.pop("embedding", None)
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [doc for _, doc in scored[:20]]
    relaxed_fields = ["keyword_match"] if results else []
    return results, relaxed_fields


@router.get("/advanced", description="Granular search designed for frontend UI filtering.")
async def advanced_search(
    name: str = Query(None, description="Partial match for product name"),
    categoryName: str = Query(None, description="Partial match for category name"),
    brandName: str = Query(None, description="Partial match for brand name")
):
    query = {}
    if name:
        query["name"] = {"$regex": name, "$options": "i"}
    if categoryName:
        category = await db.Categories.find_one({"name": {"$regex": categoryName, "$options": "i"}})
        if category:
            query["categoryId"] = category["id"]
        else:
            return []
    if brandName:
        brand = await db.Brands.find_one({"name": {"$regex": brandName, "$options": "i"}})
        if brand:
            query["brandId"] = brand["id"]
        else:
            return []
    products = await db.Products.find(query, {"_id": 0}).to_list(length=100)
    if not products:
        raise HTTPException(status_code=404, detail="No products match these specific filters.")
    return products


@router.get("/policy")
async def search_store_policy(q: str = Query(..., description="The policy question")):
    """Semantic search over store FAQs and policies."""
    query_vector = embedding_model.encode(q).tolist()
    cursor = db.StoreKnowledge.find()
    results = []
    async for doc in cursor:
        doc_vector = doc["embedding"]
        score = calculate_similarity(query_vector, doc_vector)
        doc.pop("embedding", None)
        doc["_id"] = str(doc["_id"])
        doc["similarity_score"] = float(score)
        results.append(doc)
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:3]