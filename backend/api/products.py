# backend/api/products.py
import re
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from backend.db.database import db
from sentence_transformers import SentenceTransformer
from bson.objectid import ObjectId
from bson.errors import InvalidId
from backend.api.ml_core import embedding_model

router = APIRouter()


# -------------------- Core reusable logic --------------------

def build_search_text(name, category_name, gender, description, brand_name=None):
    gender_str = gender or "unisex"
    brand_str = f" | brand: {brand_name}" if brand_name else ""
    return f"{name} | category: {category_name} | for: {gender_str}{brand_str} | {description}"


async def resolve_category(category_slug: str):
    doc = await db.Categories.find_one({"slug": category_slug})
    if doc:
        return doc["id"], doc["name"]
    return None, category_slug


async def resolve_brand(brand_name: Optional[str] = None, brand_id: Optional[str] = None):
    """
    Two ways in: a raw name (free-text callers) or a known id (dropdown callers).
    brand_id takes priority if both are given.
    """
    if brand_id:
        doc = await db.Brands.find_one({"id": brand_id})
        if doc:
            return doc["id"], doc["name"]
        return None, None  # bad id, no auto-create — dropdown should only send valid ids

    if not brand_name:
        return None, None

    clean_name = brand_name.strip()
    doc = await db.Brands.find_one(
        {"name": {"$regex": f"^{re.escape(clean_name)}$", "$options": "i"}}
    )
    if doc:
        return doc["id"], doc["name"]

    new_id = f"brand_{clean_name.lower().replace(' ', '_')}"
    await db.Brands.insert_one({"id": new_id, "name": clean_name, "slug": clean_name.lower().replace(' ', '-')})
    return new_id, clean_name


# -------------------- Request schema --------------------

class ProductWrite(BaseModel):
    name: str
    category: str
    gender: Optional[str] = "unisex"
    brand_id: Optional[str] = None
    brand_name: Optional[str] = None
    price: float
    stock: int
    image: Optional[str] = None
    description: Optional[str] = None
    warranty: Optional[str] = None
    
# -------------------- Read endpoints --------------------

@router.get("/")
async def get_all_products():
    return await db.Products.find({"status": "active"}, {"_id": 0}).to_list(length=100)


@router.get("/search")
async def search_products(q: str = Query(...)):
    regex_pattern = {"$regex": q, "$options": "i"}
    brand = await db.Brands.find_one({"name": regex_pattern})
    category = await db.Categories.find_one({"name": regex_pattern})

    or_conditions = [{"name": regex_pattern}]
    if brand:
        or_conditions.append({"brandId": brand["id"]})
    if category:
        or_conditions.append({"categoryId": category["id"]})

    products = await db.Products.find(
        {"status": "active", "$or": or_conditions}, {"_id": 0, "embedding": 0}
    ).to_list(length=100)

    if not products:
        raise HTTPException(status_code=404, detail=f"No products found for '{q}'")
    return products




@router.get("/brands")
async def list_brands(category: str = Query(None)):
    match = {}
    if category:
        cat_doc = await db.Categories.find_one({
            "$or": [
                {"slug": category},
                {"slug": {"$regex": f"^{re.escape(category)}", "$options": "i"}},
                {"name": {"$regex": re.escape(category), "$options": "i"}}
            ]
        })
        if not cat_doc:
            return []
        child_ids = await db.Categories.distinct("id", {"parentCategoryId": cat_doc["id"]})
        match["categoryId"] = {"$in": [cat_doc["id"]] + child_ids}

    brand_ids = await db.Products.distinct("brandId", {**match, "brandId": {"$ne": None}})
    brands = await db.Brands.find({"id": {"$in": brand_ids}}, {"_id": 0, "name": 1}).to_list(100)
    return [b["name"] for b in brands]





@router.get("/brands/full")
async def list_brands_full():
    brands = await db.Brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(200)
    return brands


@router.get("/name/{product_name}")
async def get_product_by_name(product_name: str):
    query = {"name": {"$regex": product_name, "$options": "i"}, "status": "active"}
    products = await db.Products.find(query, {"_id": 0, "embedding": 0}).to_list(length=10)
    if not products:
        raise HTTPException(status_code=404, detail=f"No products found containing '{product_name}'")
    return products


# -------------------- Write endpoints --------------------

@router.post("/")
async def create_product(payload: ProductWrite):
    category_id, category_name = await resolve_category(payload.category)
    brand_id, brand_name = await resolve_brand(brand_name=payload.brand_name, brand_id=payload.brand_id)

    search_text = build_search_text(payload.name, category_name, payload.gender, payload.description, brand_name)
    embedding = embedding_model.encode(search_text).tolist()

    product = {
        "id": f"prod_custom_{uuid.uuid4().hex[:6]}",
        "name": payload.name,
        "categoryId": category_id,
        "category": category_name,
        "brandId": brand_id,
        "brand": brand_name,
        "gender": payload.gender,
        "price": payload.price,
        "stock": payload.stock,
        "thumbnail": payload.image,
        "image": payload.image,
        "description": payload.description,
        "shortDescription": (payload.description or "")[:150],
        "searchText": search_text,
        "rating": 0.0,
        "totalReviews": 0,
        "warranty": payload.warranty or "No Warranty",
        "embedding": embedding,
        "createdAt": datetime.now(),
        "status": "active"
    }
    result = await db.Products.insert_one(product)

    warnings = []
    if not category_id:
        warnings.append(f'Category "{payload.category}" not recognized.')
    if payload.brand_id and not brand_id:
        warnings.append(f'Brand with ID "{payload.brand_id}" not found.')

    return {"id": product["id"], "mongo_id": str(result.inserted_id), "warnings": warnings}


@router.put("/{product_id}")
async def update_product(product_id: str, payload: ProductWrite):
    category_id, category_name = await resolve_category(payload.category)
    brand_id, brand_name = await resolve_brand(brand_name=payload.brand_name, brand_id=payload.brand_id)

    search_text = build_search_text(payload.name, category_name, payload.gender, payload.description, brand_name)
    embedding = embedding_model.encode(search_text).tolist()

    update_data = {
        "name": payload.name,
        "categoryId": category_id,
        "category": category_name,
        "brandId": brand_id,
        "brand": brand_name,
        "gender": payload.gender,
        "price": payload.price,
        "stock": payload.stock,
        "thumbnail": payload.image,
        "image": payload.image,
        "description": payload.description,
        "shortDescription": (payload.description or "")[:150],
        "searchText": search_text,
        "embedding": embedding,
        "updatedAt": datetime.now()
    }

    # result = await db.Products.update_one({"id": product_id}, {"$set": update_data})
    
    try:
        query = {"_id": ObjectId(product_id)}
    except InvalidId:
        query = {"id": product_id}

    result = await db.Products.update_one(query, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"id": product_id, "updated": True}



@router.get("/{product_id}")
async def get_product_by_id(product_id: str):
    try:
        query = {"_id": ObjectId(product_id), "status": "active"}
    except InvalidId:
        query = {"id": product_id, "status": "active"}

    product = await db.Products.find_one(query)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product["_id"] = str(product["_id"])
    return product