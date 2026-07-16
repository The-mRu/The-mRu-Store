from fastapi import APIRouter
from backend.db.database import db
router = APIRouter()

@router.get("/")
async def get_categories():
    cursor = db.Categories.find({}, {"_id": 0})
    categories = await cursor.to_list(length=None)  # await the async cursor
    return categories
