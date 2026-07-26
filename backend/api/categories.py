# backend/api/categories.py
from fastapi import APIRouter, Query 
from backend.db.database import db
router = APIRouter()

@router.get("/")
async def get_categories():
    cursor = db.Categories.find({}, {"_id": 0})
    categories = await cursor.to_list(length=None)  # await the async cursor
    return categories


@router.get("/list")
async def list_categories():
    pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$categoryId", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 0}}}
    ]
    counts = await db.Products.aggregate(pipeline).to_list(length=100)
    count_map = {c["_id"]: c["count"] for c in counts}

    categories = await db.Categories.find(
        {"id": {"$in": list(count_map.keys())}, "isActive": True},
        {"_id": 0, "id": 1, "name": 1, "description": 1}
    ).to_list(length=100)

    for cat in categories:
        cat["productCount"] = count_map.get(cat["id"], 0)

    categories.sort(key=lambda c: -c["productCount"])
    return categories

