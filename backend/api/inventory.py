from fastapi import APIRouter
from backend.db.database import db

router = APIRouter()

# @router.get("/low-stock")
# def get_low_stock_items():
#     # Queries your actual Inventory collection matching its true attributes
#     items = list(db.Inventory.find({
#         "$expr": {
#             "$lte": ["$availableStock", "$lowStockThreshold"]
#         }
#     }, {"_id": 0}))
#     return items


@router.get("/low-stock")
async def get_low_stock_items(threshold: int = 10):
    items = await db.Products.find({"stock": {"$lt": threshold}}, {"_id": 0}).to_list(length=100)
    return items