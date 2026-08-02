# backend/api/admin_analytics.py
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from backend.db.database import db


router = APIRouter()


def parse_date(date_str: str) -> datetime:
    """
    Parse a date string in any common format.
    Returns a datetime object or raises ValueError.
    
    Supported formats:
    - YYYY-MM-DD     (2026-07-28)
    - DD/MM/YYYY     (28/07/2026)
    - MM/DD/YYYY     (07/28/2026)
    - DD-MM-YYYY     (28-07-2026)
    - YYYY/MM/DD     (2026/07/28)
    - Month DD, YYYY (July 28, 2026)
    - DD Month YYYY  (28 July 2026)
    - today, yesterday, 2 days ago, last week
    """
    date_str = date_str.strip().lower()
    
    # Handle relative dates
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if date_str in ("today", "today's"):
        return now
    if date_str in ("yesterday", "yesterday's"):
        return now - timedelta(days=1)
    if date_str in ("this week", "current week"):
        return now - timedelta(days=now.weekday())  # Monday of this week
    if date_str in ("last week", "previous week"):
        return now - timedelta(days=now.weekday() + 7)
    if "days ago" in date_str:
        try:
            days = int(date_str.split()[0])
            return now - timedelta(days=days)
        except (ValueError, IndexError):
            pass
    
    # Try formats with month names
    month_formats = [
        "%B %d, %Y",      # July 28, 2026
        "%b %d, %Y",      # Jul 28, 2026
        "%d %B %Y",       # 28 July 2026
        "%d %b %Y",       # 28 Jul 2026
        "%B %d %Y",       # July 28 2026
        "%d %B, %Y",      # 28 July, 2026
    ]
    for fmt in month_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Try numeric formats
    numeric_formats = [
        "%Y-%m-%d",       # 2026-07-28
        "%d/%m/%Y",       # 28/07/2026
        "%m/%d/%Y",       # 07/28/2026
        "%d-%m-%Y",       # 28-07-2026
        "%Y/%m/%d",       # 2026/07/28
        "%d.%m.%Y",       # 28.07.2026
        "%Y%m%d",         # 20260728
    ]
    for fmt in numeric_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse date: '{date_str}'. Use YYYY-MM-DD, DD/MM/YYYY, or 'today'.")

@router.get("/summary")
async def get_business_summary(
    period: str = Query("today", description="today | yesterday | week"),
    date: str = Query(None, description="Specific date. Supports: YYYY-MM-DD, DD/MM/YYYY, 'today', 'yesterday', 'July 28, 2026', '2 days ago', etc.")
):
    now = datetime.utcnow()

    if date:
        try:
            start = parse_date(date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        end = start + timedelta(days=1)
    elif period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "yesterday":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "week":
        start = now - timedelta(days=7)
        end = now
    else:
        raise HTTPException(status_code=400, detail="period must be 'today', 'yesterday', or 'week'.")

    total_orders = await db.Orders.count_documents({"orderedAt": {"$gte": start, "$lt": end}})
    pending = await db.Orders.count_documents({"orderedAt": {"$gte": start, "$lt": end}, "status": "Processing"})
    cancelled = await db.Orders.count_documents({"orderedAt": {"$gte": start, "$lt": end}, "status": "Cancelled"})

    revenue_pipeline = [
        {"$match": {"orderedAt": {"$gte": start, "$lt": end}, "status": {"$ne": "Cancelled"}}},
        {"$group": {"_id": None, "total": {"$sum": "$totalAmount"}}}
    ]
    revenue_result = await db.Orders.aggregate(revenue_pipeline).to_list(1)
    revenue = revenue_result[0]["total"] if revenue_result else 0

    new_customers = await db.Users.count_documents({"createdAt": {"$gte": start, "$lt": end}})

    # Only include current low stock for "today" — not meaningful for historical/future dates
    is_today = (start.date() == now.date())
    low_stock = await db.Products.count_documents({"stock": {"$lte": 10}, "status": "active"}) if is_today else None

    result = {
        "period_start": start.strftime("%Y-%m-%d"),
        "period_end": end.strftime("%Y-%m-%d"),
        "total_orders": total_orders,
        "revenue": round(revenue, 2),
        "new_customers": new_customers,
        "pending_orders": pending,
        "cancelled_orders": cancelled,
    }

    if is_today:
        result["low_stock_alerts"] = low_stock
    else:
        result["low_stock_alerts"] = None
        result["low_stock_note"] = "Low stock data is only available for today's date."

    return result

@router.get("/analytics")
async def get_sales_analytics(compare: str = None):
    now = datetime.utcnow()
    this_week_start = now - timedelta(days=7)

    pipeline = [
        {"$match": {"orderedAt": {"$gte": this_week_start}, "status": {"$ne": "Cancelled"}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$orderedAt"}},
            "revenue": {"$sum": "$totalAmount"},
            "orders": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily = await db.Orders.aggregate(pipeline).to_list(30)
    best_day = max(daily, key=lambda d: d["revenue"]) if daily else None

    result = {"daily_breakdown": daily, "best_sales_day": best_day}

    if compare == "last_month":
        last_month_start = now - timedelta(days=60)
        last_month_end = now - timedelta(days=30)
        last_month_pipeline = [
            {"$match": {"orderedAt": {"$gte": last_month_start, "$lt": last_month_end}, "status": {"$ne": "Cancelled"}}},
            {"$group": {"_id": None, "revenue": {"$sum": "$totalAmount"}}}
        ]
        last_month = await db.Orders.aggregate(last_month_pipeline).to_list(1)
        result["last_month_revenue"] = last_month[0]["revenue"] if last_month else 0

    return result


@router.get("/top-products")
async def get_top_selling_products(limit: int = 5, order: str = "best"):
    pipeline = [
        {"$group": {"_id": "$productId", "total_sold": {"$sum": "$quantity"}}},
        {"$sort": {"total_sold": -1 if order == "best" else 1}},
        {"$limit": limit}
    ]
    results = await db.OrderItems.aggregate(pipeline).to_list(limit)

    product_ids = [r["_id"] for r in results]
    products = await db.Products.find({"id": {"$in": product_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(product_ids))
    product_lookup = {p["id"]: p["name"] for p in products}

    return {
        "products": [
            {"name": product_lookup.get(r["_id"], "Unknown product"), "units_sold": r["total_sold"]}
            for r in results
        ]
    }