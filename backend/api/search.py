# backend/api/search.py
import re
import math
from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from backend.db.database import db
from sentence_transformers import SentenceTransformer
from backend.api.ml_core import embedding_model

router = APIRouter()


def calculate_similarity(v1, v2):
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    if magnitude1 * magnitude2 == 0:
        return 0
    return dot_product / (magnitude1 * magnitude2)


def rerank_rrf(vector_results, text_results, k=60):
    scores = defaultdict(float)
    all_docs = {}

    for rank, doc in enumerate(vector_results):
        doc_id = str(doc["_id"])
        scores[doc_id] += 1 / (k + rank)
        all_docs[doc_id] = doc

    for rank, doc in enumerate(text_results):
        doc_id = str(doc["_id"])
        scores[doc_id] += 1 / (k + rank)
        all_docs[doc_id] = doc

    ranked_ids = sorted(scores.keys(), key=lambda d_id: scores[d_id], reverse=True)

    final_results = []
    for d_id in ranked_ids:
        doc = all_docs[d_id]
        doc.pop("embedding", None)
        doc["_id"] = str(doc["_id"])
        final_results.append(doc)

    return final_results


async def resolve_category_id(category_name: str):
    """Returns categoryId(s) to filter by — includes subcategories if the match is a parent category."""
    doc = await db.Categories.find_one(
        {"$or": [
            {"name": {"$regex": f"^{re.escape(category_name)}$", "$options": "i"}},
            {"slug": category_name}
        ]}
    )
    if not doc:
        return None

    child_ids = await db.Categories.distinct("id", {"parentCategoryId": doc["id"]})
    if child_ids:
        return {"$in": [doc["id"]] + child_ids}
    return doc["id"]

async def resolve_brand_id(brand_name: str):
    doc = await db.Brands.find_one(
        {"name": {"$regex": f"^{re.escape(brand_name)}$", "$options": "i"}}
    )
    return doc["id"] if doc else None

async def resolve_warranty_id(warranty_name: str):
    doc = await db.Warranties.find_one(
        {"name": {"$regex": f"^{re.escape(warranty_name)}$", "$options": "i"}}
    )
    return doc["id"] if doc else None

async def _run_search(q, category, gender, brand, min_price, max_price) -> list:
    print(f"🔥🔥🔥 _run_search CALLED with brand={brand!r}, category={category!r}, q={q!r} 🔥🔥🔥") #testing perpose

    hard_filter = {"status": "active"}

    if gender:
        hard_filter["gender"] = {"$in": [gender.lower(), "unisex"]}

    if category:
        cat_id = await resolve_category_id(category)
        if cat_id:
            hard_filter["categoryId"] = cat_id
        else:
            return []

    if brand:
        brand_id = await resolve_brand_id(brand)
        if brand_id:
            hard_filter["brandId"] = brand_id 
            print(f"🔥🔥🔥 resolve_brand_id({brand!r}) returned: {brand_id!r}")
        else:
            print("🔥🔥🔥 RETURNING EMPTY — brand did not resolve")
            return []

    if min_price is not None or max_price is not None:
        hard_filter["price"] = {}
        if min_price is not None:
            hard_filter["price"]["$gte"] = min_price
        if max_price is not None:
            hard_filter["price"]["$lte"] = max_price

    DEFAULT_THUMBNAIL = "/static/images/placeholder.png"

    def _apply_defaults(product):
        product.setdefault("thumbnail", DEFAULT_THUMBNAIL)
        if not product.get("thumbnail"):
            product["thumbnail"] = DEFAULT_THUMBNAIL
        product.setdefault("discountPrice", None)
        product.setdefault("rating", 0.0)
        return product

    if not q:
        filter_only_results = await db.Products.find(hard_filter).limit(20).to_list(20)
        if not filter_only_results:
            return []
        for product in filter_only_results:
            product.pop("embedding", None)
            product["_id"] = str(product["_id"])
            _apply_defaults(product)
        return filter_only_results[:20]

    text_results = []
    text_query = {**hard_filter, "$text": {"$search": q}}
    text_cursor = db.Products.find(text_query, {"score": {"$meta": "textScore"}})
    text_cursor = text_cursor.sort([("score", {"$meta": "textScore"})]).limit(50)
    text_results = await text_cursor.to_list(length=50)

    query_vector = embedding_model.encode(q).tolist()
    candidate_docs = await db.Products.find(hard_filter).to_list(length=300)
    scored_docs = []

    for doc in candidate_docs:
        vec = doc.get("embedding")
        if not vec:
            continue
        score = calculate_similarity(query_vector, vec)
        if score > 0.25:
            doc["vectorScore"] = score
            scored_docs.append(doc)

    scored_docs.sort(key=lambda x: x["vectorScore"], reverse=True)
    vector_results = scored_docs[:50]

    if not text_results and not vector_results:
        return []

    final_ranked_list = rerank_rrf(vector_results, text_results)

    for product in final_ranked_list:
        _apply_defaults(product)

    return final_ranked_list[:20]


async def search_products_core(
    q: Optional[str] = None,
    category: Optional[str] = None,
    gender: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
) -> dict:
    """Returns {"products": [...], "relaxed": [...]}."""
    results = await _run_search(q, category, gender, brand, min_price, max_price)
    if results:
        return {"products": results, "relaxed": []}

    relaxed_applied = []
    current = {"q": q, "category": category, "gender": gender, "brand": brand,
               "min_price": min_price, "max_price": max_price}

    relax_order = ["gender", "price"]
    for field in relax_order:
        if field == "price":
            if current["min_price"] is None and current["max_price"] is None:
                continue
            current["min_price"] = None
            current["max_price"] = None
        else:
            if not current.get(field):
                continue
            current[field] = None

        relaxed_applied.append(field)
        results = await _run_search(**current)
        if results:
            return {"products": results, "relaxed": relaxed_applied}

    return {"products": [], "relaxed": relaxed_applied}


@router.get("/")
async def ai_omni_search(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
):
    result = await search_products_core(
        q=q, category=category, gender=gender, brand=brand,
        min_price=min_price, max_price=max_price
    )
    if not result["products"]:
        raise HTTPException(status_code=404, detail="No products found matching these criteria.")
    return result


@router.get("/advanced", description="Granular search designed for frontend UI filtering.")
async def advanced_search(
    name: str = Query(None),
    categoryName: str = Query(None),
    brandName: str = Query(None)
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