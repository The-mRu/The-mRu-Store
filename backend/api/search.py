# backend/api/search.py
import re
import math
from collections import defaultdict
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from backend.db.database import db
from sentence_transformers import SentenceTransformer

router = APIRouter()

print("Loading AI Search Model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')


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
    """
    Returns categoryId(s) to filter by. Matches slug, partial slug, or name —
    and if the match is a parent category, expands to include its subcategories
    (e.g. 'electronics' or 'laptop' both correctly pull in 'Computers & Laptops').
    """
    doc = await db.Categories.find_one({
        "$or": [
            {"slug": category_name},
            {"slug": {"$regex": f"^{re.escape(category_name)}", "$options": "i"}},
            {"name": {"$regex": re.escape(category_name), "$options": "i"}}
        ]
    })
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

async def _lexical_search(hard_filter, q, limit=50):
    """
    Unified lexical search: $text AND regex merged into ONE scored list,
    so every candidate has a comparable score before RRF runs — fixes the
    old bug where regex results were appended unscored at the end and
    effectively invisible to ranking.
    """
    text_scores = {}
    try:
        text_query = {**hard_filter, "$text": {"$search": q}}
        text_cursor = db.Products.find(text_query, {"score": {"$meta": "textScore"}})
        text_cursor = text_cursor.sort([("score", {"$meta": "textScore"})]).limit(limit)
        text_docs = await text_cursor.to_list(length=limit)
        for d in text_docs:
            text_scores[str(d["_id"])] = d.get("score", 0)
    except Exception:
        text_docs = []

    keywords = [w for w in q.lower().split() if len(w) > 2] or [q.lower()]
    regex_conditions = [
        {"$or": [
            {"name": {"$regex": kw, "$options": "i"}},
            {"category": {"$regex": kw, "$options": "i"}},
            {"description": {"$regex": kw, "$options": "i"}},
            {"shortDescription": {"$regex": kw, "$options": "i"}},
        ]} for kw in keywords
    ]
    regex_query = {**hard_filter, "$and": regex_conditions} if regex_conditions else hard_filter
    regex_docs = await db.Products.find(regex_query).limit(limit).to_list(length=limit)

    regex_scores = {}
    for doc in regex_docs:
        haystack = " ".join([
            str(doc.get("name", "")), str(doc.get("category", "")),
            str(doc.get("description", "")), str(doc.get("shortDescription", ""))
        ]).lower()
        match_count = sum(1 for kw in keywords if kw in haystack)
        regex_scores[str(doc["_id"])] = match_count / len(keywords)

    all_docs = {str(d["_id"]): d for d in text_docs + regex_docs}
    combined_scores = {
        doc_id: text_scores.get(doc_id, 0) * 0.6 + regex_scores.get(doc_id, 0) * 0.4
        for doc_id in all_docs
    }
    ranked_ids = sorted(combined_scores.keys(), key=lambda i: combined_scores[i], reverse=True)
    return [all_docs[doc_id] for doc_id in ranked_ids[:limit]]


async def _run_search(q, category, gender, brand, min_price, max_price) -> list:
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
        else:
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

    # --- Unified lexical search (fixes Problems 1-4) ---
    lexical_results = await _lexical_search(hard_filter, q, limit=50)

    # --- Vector search ---
    # Embedding similarity on short, templated product names doesn't reliably
    # separate real matches from noise (confirmed via diagnostic: unrelated
    # products like monitors/coffee makers scored HIGHER than genuinely
    # relevant ones for the same query — no threshold fixes this). So vector
    # search is only used in two safe ways:
    #   1. To re-score docs lexical search already found (helps RRF order
    #      the best fit among known-relevant results).
    #   2. As a fallback over a wider, unvetted pool ONLY when lexical search
    #      found few/no results — same "relax only when needed" principle
    #      already used in search_products_core's relaxation logic.
    query_vector = embedding_model.encode(q).tolist()

    scored_docs = []
    for doc in lexical_results:
        vec = doc.get("embedding")
        if not vec:
            continue
        score = calculate_similarity(query_vector, vec)
        doc["vectorScore"] = score
        scored_docs.append(doc)

    LEXICAL_WEAK_THRESHOLD = 5  # below this, lexical search is considered "thin"
    RANDOM_POOL_MIN_SCORE = 0.6  # high bar — this pool is unfiltered/unvetted

    if len(lexical_results) < LEXICAL_WEAK_THRESHOLD:
        lexical_ids = [d["_id"] for d in lexical_results]
        random_sample = await db.Products.find(
            {**hard_filter, "_id": {"$nin": lexical_ids}}
        ).limit(250).to_list(250)

        for doc in random_sample:
            vec = doc.get("embedding")
            if not vec:
                continue
            score = calculate_similarity(query_vector, vec)
            if score > RANDOM_POOL_MIN_SCORE:
                doc["vectorScore"] = score
                scored_docs.append(doc)

    scored_docs.sort(key=lambda x: x["vectorScore"], reverse=True)
    vector_results = scored_docs[:100]

    if not lexical_results and not vector_results:
        return []

    final_ranked_list = rerank_rrf(vector_results, lexical_results)

    for product in final_ranked_list:
        _apply_defaults(product)

    return final_ranked_list[:50]

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

    relax_order = ["gender", "price"]   # brand and category are hard identity constraints — never auto-relaxed
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
    limit: int = Query(10),
    offset: int = Query(0),
):
    result = await search_products_core(
        q=q, category=category, gender=gender, brand=brand,
        min_price=min_price, max_price=max_price
    )
    if not result["products"]:
        raise HTTPException(status_code=404, detail="No products found matching these criteria.")
    
    all_products = result["products"]
    total = len(all_products)
    paginated = all_products[offset:offset + limit]
    
    return {
        "products": paginated,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + limit) < total,
        "relaxed": result.get("relaxed", [])
    }


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