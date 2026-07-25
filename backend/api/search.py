#backend/api/search.py
from fastapi import APIRouter, HTTPException, Query
from backend.db.database import db
from sentence_transformers import SentenceTransformer
import math

from typing import Optional
import re

router = APIRouter()


print("Loading AI Search Model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
# -------------------------------------------------------

def calculate_similarity(v1, v2):
    """A standard math formula (Cosine Similarity) to see how close two lists of numbers are."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    if magnitude1 * magnitude2 == 0: return 0
    return dot_product / (magnitude1 * magnitude2)




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

    # 1. Process Keyword Search (q)
    if q:
        # Trim trailing 's' / 'es' from words to match singular/plural (e.g., 'laptops' -> 'laptop')
        words = [re.sub(r'(s|es)$', '', w, flags=re.IGNORECASE) for w in q.strip().split() if len(w) > 1]
        
        if words:
            # Match ALL keywords anywhere in product name, shortDescription, or description
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

    # 2. Process Brand Filter
    if brand:
        # Strip trailing 's' and perform case-insensitive regex match
        clean_brand = re.sub(r'(s|es)$', '', brand.strip(), flags=re.IGNORECASE)
        b = await db.Brands.find_one({"name": {"$regex": clean_brand, "$options": "i"}})
        if b:
            and_conditions.append({"brandId": b["id"]})
        else:
            # Fallback: Search for the brand word inside product name if brand document wasn't found
            and_conditions.append({"name": {"$regex": clean_brand, "$options": "i"}})

    # 3. Process Category Filter
    if category:
        clean_category = re.sub(r'(s|es)$', '', category.strip(), flags=re.IGNORECASE)
        c = await db.Categories.find_one({"name": {"$regex": clean_category, "$options": "i"}})
        if c:
            and_conditions.append({"categoryId": c["id"]})
        else:
            # Fallback: Search for category word inside product name or description
            and_conditions.append({
                "$or": [
                    {"name": {"$regex": clean_category, "$options": "i"}},
                    {"description": {"$regex": clean_category, "$options": "i"}}
                ]
            })

    # 4. Price Range Filters
    if min_price is not None or max_price is not None:
        price_query = {}
        if min_price is not None:
            price_query["$gte"] = min_price
        if max_price is not None:
            price_query["$lte"] = max_price
        and_conditions.append({"price": price_query})

    # Combine all AND conditions
    if and_conditions:
        query["$and"] = and_conditions

    # Execute MongoDB Query
    products = await db.Products.find(query, {"_id": 0}).to_list(length=100)
    
    # 5. Ultimate Fallback Search (If strict match returns empty, search full text of q)
    if not products and q:
        fallback_words = q.strip().split()
        fallback_conditions = [
            {"name": {"$regex": w, "$options": "i"}} for w in fallback_words
        ]
        products = await db.Products.find({"$or": fallback_conditions}, {"_id": 0}).to_list(length=100)

    if not products:
        raise HTTPException(status_code=404, detail="No products found matching these criteria.")
    
    # 6. Ensure all products have default fallback keys for the UI
    DEFAULT_THUMBNAIL = "/static/images/placeholder.png"  # Adjust path to your static fallback image

    for product in products:
        if "thumbnail" not in product or not product["thumbnail"]:
            product["thumbnail"] = DEFAULT_THUMBNAIL
            
        if "discountPrice" not in product:
            product["discountPrice"] = None
            
        if "rating" not in product:
            product["rating"] = 0.0

    return products





@router.get("/advanced", description="Granular search designed for frontend UI filtering.")
async def advanced_search(
    name: str = Query(None, description="Partial match for product name"),
    categoryName: str = Query(None, description="Partial match for category name"),
    brandName: str = Query(None, description="Partial match for brand name")
):
    query = {}
    
    # 1. Add Name Filter
    if name:
        query["name"] = {"$regex": name, "$options": "i"}

    # 2. Add Category Filter (Translates Name -> ID)
    if categoryName:
        category = await db.Categories.find_one({"name": {"$regex": categoryName, "$options": "i"}})
        if category:
            query["categoryId"] = category["id"]
        else:
            # If category name doesn't exist, combination yields no products
            return [] 

    # 3. Add Brand Filter (Translates Name -> ID)
    if brandName:
        brand = await db.Brands.find_one({"name": {"$regex": brandName, "$options": "i"}})
        if brand:
            query["brandId"] = brand["id"]
        else:
            # If brand name doesn't exist, combination yields no products
            return [] 

    # 4. Execute the combined strict query
    products = await db.Products.find(query, {"_id": 0}).to_list(length=100)
    
    if not products:
        raise HTTPException(status_code=404, detail="No products match these specific filters.")
        
    return products

@router.get("/policy")
async def search_store_policy(q: str = Query(..., description="The policy question")):
    """Searches the StoreKnowledge collection for FAQs and Policies."""
    # 1. Translate the user's question into 384 numbers
    query_vector = embedding_model.encode(q).tolist()

    # 2. Grab all policy paragraphs from MongoDB
    cursor = db.StoreKnowledge.find()
    
    results = []
    async for doc in cursor:
        # 3. Compare the numbers using the formula we already built
        doc_vector = doc["embedding"]
        score = calculate_similarity(query_vector, doc_vector)
        
        # 4. Hide the massive numbers to protect the API
        doc.pop("embedding", None)
        doc["_id"] = str(doc["_id"]) 
        doc["similarity_score"] = float(score)
        
        results.append(doc)

    # 5. Sort by highest score first and grab the Top 3 best matches
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:3] # Top 3 paragraphs are usually enough to answer a question!