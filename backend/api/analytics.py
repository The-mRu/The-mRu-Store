from fastapi import APIRouter
from backend.db.database import db  # now using Motor's AsyncIOMotorClient

router = APIRouter()

@router.get("/dashboard")
async def get_dashboard_metrics():
    total_products = await db.Products.count_documents({})
    total_orders = await db.Orders.count_documents({})
    total_users = await db.Users.count_documents({})
    return {
        "totalProducts": total_products,
        "totalOrders": total_orders,
        "totalUsers": total_users
    }

@router.get("/top-products")
async def get_top_products(limit: int = 5):
    cursor = db.Products.find({}, {"_id": 0}).sort("sales", -1).limit(limit)
    products = await cursor.to_list(length=limit)
    return products

@router.get("/sales")
async def get_sales_summary():
    pipeline = [
        {"$group": {"_id": None, "totalSales": {"$sum": "$amount"}}}
    ]
    cursor = db.Orders.aggregate(pipeline)
    sales = await cursor.to_list(length=1)
    return sales[0] if sales else {"totalSales": 0}
