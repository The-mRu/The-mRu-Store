#backend/api/products.py  
from fastapi import APIRouter, HTTPException, Query
from backend.db.database import db

router = APIRouter()

@router.get("/")
async def get_all_products():
    products = await db.Products.find({}, {"_id": 0}).to_list(length=100)
    return products

@router.get("/search")
async def search_products(
    q: str = Query(..., description="A general search term (e.g., 'Samsung', 'Jeans', 'Electronics')")
):
    # 1. Create a loose, case-insensitive regex from the search term
    regex_pattern = {"$regex": q, "$options": "i"}

    # 2. Try to find matching Brands or Categories just in case
    brand = await db.Brands.find_one({"name": regex_pattern})
    category = await db.Categories.find_one({"name": regex_pattern})

    # 3. Build a massive OR condition
    # It will find the product if 'q' matches the product name, OR the brand ID, OR the category ID
    or_conditions = [
        {"name": regex_pattern}
    ]
    
    if brand:
        or_conditions.append({"brandId": brand["id"]})
    if category:
        or_conditions.append({"categoryId": category["id"]})

    # 4. Execute the query
    # products = await db.Products.find({"$or": or_conditions}, {"_id": 0}).to_list(length=100)
    products = await db.Products.find({}, {"_id": 0, "embedding": 0}).to_list(length=100)
    
    if not products:
        raise HTTPException(status_code=404, detail=f"No products found for '{q}'")
        
    return products

@router.get("/brands")
async def list_brands(category: str = Query(None)):
    match = {}
    if category:
        cat_doc = await db.Categories.find_one({"slug": category})
        if cat_doc:
            # Include this category AND any subcategories under it
            child_ids = await db.Categories.distinct("id", {"parentCategoryId": cat_doc["id"]})
            match["categoryId"] = {"$in": [cat_doc["id"]] + child_ids}

    brand_ids = await db.Products.distinct("brandId", {**match, "brandId": {"$ne": None}})
    brands = await db.Brands.find({"id": {"$in": brand_ids}}, {"_id": 0, "name": 1}).to_list(100)
    return [b["name"] for b in brands]

## Single product endpoint
@router.get("/{product_id}")
async def get_product_by_id(product_id: str):
    product = await db.Products.find_one({"id": product_id}, {"_id": 0})
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/name/{product_name}")
async def get_product_by_name(product_name: str):
    # 1. Use $regex with "$options": "i" for a partial, case-insensitive match
    query = {"name": {"$regex": product_name, "$options": "i"}}
    
    # 2. Hide both the _id and the massive embedding array
    projection = {"_id": 0, "embedding": 0}
    
    # 3. Return up to 10 matching products (in case they search a broad word like "shirt")
    products = await db.Products.find(query, projection).to_list(length=10)
    
    if not products:
        raise HTTPException(status_code=404, detail=f"No products found containing '{product_name}'")
        
    return products