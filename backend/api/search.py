from fastapi import APIRouter, HTTPException, Query
from backend.db.database import db
from sentence_transformers import SentenceTransformer
import math

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



@router.get("/", description="Omnibox search designed for AI Agents. Searches across product names, categories, and brands simultaneously.")
async def ai_omni_search(
    q: str = Query(..., description="A general search term (e.g., 'Samsung', 'Jeans', 'Electronics')")
):
    # 1. Create a loose, case-insensitive regex from the search term
    regex_pattern = {"$regex": q, "$options": "i"}

    # 2. Check if the search term matches any Brands or Categories
    brand = await db.Brands.find_one({"name": regex_pattern})
    category = await db.Categories.find_one({"name": regex_pattern})

    # 3. Build a massive OR condition
    or_conditions = [
        {"name": regex_pattern}
    ]
    
    if brand:
        or_conditions.append({"brandId": brand["id"]})
    if category:
        or_conditions.append({"categoryId": category["id"]})

    # 4. Execute the query
    products = await db.Products.find({"$or": or_conditions}, {"_id": 0}).to_list(length=100)
    
    if not products:
        raise HTTPException(status_code=404, detail=f"No products found for '{q}'")
        
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