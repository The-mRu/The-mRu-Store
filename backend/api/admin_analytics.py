# backend/api/admin_analytics.py
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta, UTC
from backend.db.database import db
import re


router = APIRouter()

print(datetime.now(UTC)) 
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
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
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
    now = datetime.now(UTC)

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

    # new_customers = await db.Users.count_documents({"createdAt": {"$gte": start, "$lt": end}})
    new_customers = await db.Users.count_documents({"created_at": {"$gte": start, "$lt": end}})
    
    

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
    now = datetime.now(UTC)
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
async def get_top_selling_products(
    start_date: str = Query(None, description="Start of the range, e.g. '2026-01-01', 'this week', 'last month', 'all time'"),
    end_date: str = Query(None, description="End of the range, defaults to now if not given"),
    limit: int = Query(10),
    min_units: int = Query(1)
):
    now = datetime.now(UTC)
    limit = max(limit, 3)

    # --- Resolve start_date ---
    if not start_date or start_date.strip().lower() in ("all time", "all_time", "ever", "always", "alltime", "all-time"):
        start = datetime(2000, 1, 1)
        period_label = "all time"
    else:
        try:
            start = parse_date(start_date)
            period_label = start_date.strip()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid start_date: {e}")

    # --- Resolve end_date ---
    if end_date:
        try:
            end = parse_date(end_date) + timedelta(days=1)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid end_date: {e}")
    else:
        end = now

    # --- Aggregate OrderItems ---
    pipeline = [
        {
            "$lookup": {
                "from": "Orders",
                "localField": "orderId",
                "foreignField": "id",
                "as": "order"
            }
        },
        {"$unwind": "$order"},
        {"$match": {"order.orderedAt": {"$gte": start, "$lt": end}}},
        {"$group": {
            "_id": "$productId",
            "total_sold": {"$sum": "$quantity"},
            "total_revenue": {"$sum": "$totalPrice"}
        }},
        {"$match": {"total_sold": {"$gte": min_units}}},
        {"$sort": {"total_sold": -1}},
        {"$limit": limit}
    ]
    top_items = await db.OrderItems.aggregate(pipeline).to_list(limit)

    # --- Enrich with product details ---
    product_ids = [item["_id"] for item in top_items]
    product_map = {}
    if product_ids:
        products = await db.Products.find(
            {"id": {"$in": product_ids}},
            {"_id": 0, "id": 1, "name": 1, "price": 1, "thumbnail": 1, "stock": 1}
        ).to_list(len(product_ids))
        product_map = {p["id"]: p for p in products}

    result = []
    for item in top_items:
        product = product_map.get(item["_id"], {})
        result.append({
            "product_id": item["_id"],
            "name": product.get("name", "Unknown Product"),
            "units_sold": item["total_sold"],
            "revenue": round(item["total_revenue"], 2),
            "current_price": product.get("price"),
            "current_stock": product.get("stock", 0),
        })

    # --- Count total unique products sold (before min_units filter) ---
    total_pipeline = [
        {
            "$lookup": {
                "from": "Orders",
                "localField": "orderId",
                "foreignField": "id",
                "as": "order"
            }
        },
        {"$unwind": "$order"},
        {"$match": {"order.orderedAt": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": "$productId"}},
        {"$count": "total"}
    ]
    total_result = await db.OrderItems.aggregate(total_pipeline).to_list(1)
    total_unique_products = total_result[0]["total"] if total_result else 0

    # --- Build response ---
    response = {
        "period": period_label,
        "period_start": start.strftime("%Y-%m-%d"),
        "period_end": end.strftime("%Y-%m-%d"),
        "total_unique_products_sold": total_unique_products,
        "min_units_threshold": min_units,
        "top_products": result,
    }

    # --- Contextual notes ---
    if not result:
        response["message"] = f"No products sold {min_units}+ units in this period."
        if total_unique_products > 0:
            response["message"] += f" {total_unique_products} products sold fewer than {min_units} units."
    elif total_unique_products < 5:
        response["note"] = "Limited sales data for this period. Rankings reflect all available data."

    return response

# backend/api/admin_analytics.py — add a resolve step
@router.get("/resolve-product")
async def resolve_product_name(product_name: str = Query(...)):
    """Resolve a product name to its real id — admin equivalent of the customer-side registry lookup."""
    product = await db.Products.find_one(
        {"name": {"$regex": re.escape(product_name), "$options": "i"}},  # NOT anchored — matches anywhere in the name
        {"_id": 0, "id": 1, "name": 1}
    )
    if not product:
        raise HTTPException(status_code=404, detail=f"No product found matching '{product_name}'.")
    return product


@router.get("/product-performance")
async def get_product_performance(product_id: str = Query(...)):
    """Now takes a real product_id, not a name — resolution happens upstream."""
    product = await db.Products.find_one(
        {"id": product_id},
        {"_id": 0, "id": 1, "name": 1, "price": 1, "discountPrice": 1, "rating": 1, "totalReviews": 1, "stock": 1, "categoryId": 1, "brandId": 1}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    product_id = product["id"]

    # Sales history via the same $lookup pattern used in top-products
    sales_pipeline = [
        {"$match": {"productId": product_id}},
        {"$lookup": {"from": "Orders", "localField": "orderId", "foreignField": "id", "as": "order"}},
        {"$unwind": "$order"},
        {"$group": {
            "_id": None,
            "total_sold": {"$sum": "$quantity"},
            "total_revenue": {"$sum": "$totalPrice"},
            "first_sale": {"$min": "$order.orderedAt"},
            "last_sale": {"$max": "$order.orderedAt"}
        }}
    ]
    sales_result = await db.OrderItems.aggregate(sales_pipeline).to_list(1)
    sales = sales_result[0] if sales_result else {"total_sold": 0, "total_revenue": 0, "first_sale": None, "last_sale": None}

    # Category average price, for price-competitiveness context
    category_avg_pipeline = [
        {"$match": {"categoryId": product.get("categoryId"), "status": "active"}},
        {"$group": {"_id": None, "avg_price": {"$avg": "$price"}}}
    ]
    category_avg_result = await db.Products.aggregate(category_avg_pipeline).to_list(1)
    category_avg_price = category_avg_result[0]["avg_price"] if category_avg_result else None

    # Recent review comments, for qualitative signal
    recent_reviews = await db.Reviews.find(
        {"productId": product_id}, {"_id": 0, "rating": 1, "comment": 1}
    ).sort("createdAt", -1).limit(5).to_list(5)

    return {
        "product_name": product["name"],
        "price": product.get("price"),
        "discount_price": product.get("discountPrice"),
        "category_average_price": round(category_avg_price, 2) if category_avg_price else None,
        "current_stock": product.get("stock", 0),
        "rating": product.get("rating", 0.0),
        "total_reviews": product.get("totalReviews", 0),
        "recent_review_comments": [r["comment"] for r in recent_reviews],
        "total_units_sold": sales.get("total_sold", 0),
        "total_revenue": round(sales.get("total_revenue", 0), 2),
        "first_sale_date": sales["first_sale"].strftime("%Y-%m-%d") if sales.get("first_sale") else None,
        "last_sale_date": sales["last_sale"].strftime("%Y-%m-%d") if sales.get("last_sale") else None,
    }
    
@router.get("/inventory-alerts")
async def get_inventory_alerts(low_stock_threshold: int = 10):
    out_of_stock = await db.Products.find(
        {"stock": 0, "status": "active"}, {"_id": 0, "id": 1, "name": 1, "stock": 1}
    ).to_list(50)

    low_stock = await db.Products.find(
        {"stock": {"$gt": 0, "$lte": low_stock_threshold}, "status": "active"},
        {"_id": 0, "id": 1, "name": 1, "stock": 1}
    ).sort("stock", 1).to_list(50)

    # "Will run out soon" — products with meaningful recent sales velocity vs low remaining stock
    velocity_pipeline = [
        {"$lookup": {"from": "Orders", "localField": "orderId", "foreignField": "id", "as": "order"}},
        {"$unwind": "$order"},
        {"$match": {"order.orderedAt": {"$gte": datetime.now(UTC) - timedelta(days=30)}}},
        {"$group": {"_id": "$productId", "sold_last_30d": {"$sum": "$quantity"}}}
    ]
    velocity = await db.OrderItems.aggregate(velocity_pipeline).to_list(200)
    velocity_map = {v["_id"]: v["sold_last_30d"] for v in velocity}

    at_risk = []
    for p in low_stock:
        sold = velocity_map.get(p["id"], 0)
        if sold > 0:
            days_of_stock_left = round((p["stock"] / sold) * 30, 1) if sold else None
            at_risk.append({**p, "sold_last_30_days": sold, "estimated_days_of_stock_left": days_of_stock_left})

    return {
    "has_out_of_stock_items": len(out_of_stock) > 0,
    "out_of_stock_count": len(out_of_stock),
    "out_of_stock": out_of_stock,
    "has_low_stock_items": len(low_stock) > 0,
    "low_stock_count": len(low_stock),
    "low_stock": low_stock,
    "at_risk_of_stockout_soon": at_risk
}
    
@router.get("/tickets-summary")
async def get_pending_tickets_summary():
    """Get a summary of open support tickets — urgent, oldest unanswered, and unassigned."""
    open_tickets = await db.SupportTickets.find(
        {"status": {"$in": ["open", "under review"]}},
        {"_id": 0, "id": 1, "subject": 1, "status": 1, "priority": 1, "createdAt": 1, "assignedAdmin": 1, "userId": 1}
    ).sort("createdAt", 1).to_list(100)

    # Get user contact info for all ticket owners
    user_ids = list(set(t["userId"] for t in open_tickets if t.get("userId")))
    user_map = {}
    if user_ids:
        users = await db.Users.find(
            {"id": {"$in": user_ids}},
            {"_id": 0, "id": 1, "name": 1, "email": 1}
        ).to_list(len(user_ids))
        user_map = {u["id"]: u for u in users}

    def attach_user(ticket):
        user = user_map.get(ticket.get("userId"), {})
        return {
            "ticket_id": ticket.get("id"),
            "subject": ticket.get("subject", "No Subject"),
            "status": ticket.get("status"),
            "priority": ticket.get("priority", "normal"),
            "assigned_admin": ticket.get("assignedAdmin"),
            "created_at": ticket["createdAt"].strftime("%B %d, %Y") if ticket.get("createdAt") else None,
            "user_name": user.get("name", "Unknown"),
            "user_email": user.get("email", "No email"),
        }

    urgent_tickets = [attach_user(t) for t in open_tickets if t.get("priority") == "urgent"]
    urgent_ids = {t["ticket_id"] for t in urgent_tickets}
    unassigned = [attach_user(t) for t in open_tickets if t.get("assignedAdmin") in (None, "unassigned")]
    oldest_unanswered = [attach_user(t) for t in open_tickets if t["id"] not in urgent_ids][:5]

    return {
        "has_open_tickets": len(open_tickets) > 0,
        "total_open_tickets": len(open_tickets),
        "has_urgent_tickets": len(urgent_tickets) > 0,
        "total_urgent_tickets": len(urgent_tickets),
        "urgent_tickets": urgent_tickets,
        "oldest_unanswered": oldest_unanswered,
        "has_unassigned_tickets": len(unassigned) > 0,
        "unassigned_tickets": unassigned[:5],
    }
    
@router.get("/order-status-breakdown")
async def get_order_status_breakdown(
    start_date: str = Query(None, description="Start of range. Defaults to past week."),
    end_date: str = Query(None, description="End of range. Defaults to now.")
):
    now = datetime.now(UTC)

    if start_date:
        try:
            start = parse_date(start_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        start = now - timedelta(days=7)

    end = parse_date(end_date) + timedelta(days=1) if end_date else now

    # Status breakdown
    pipeline = [
        {"$match": {"orderedAt": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    results = await db.Orders.aggregate(pipeline).to_list(20)
    breakdown = {r["_id"]: r["count"] for r in results}

    stuck_processing = breakdown.get("Processing", 0)

    # Actual stuck orders with details
    stuck_orders = []
    if stuck_processing > 0:
        raw_orders = await db.Orders.find(
            {"orderedAt": {"$gte": start, "$lt": end}, "status": "Processing"},
            {"_id": 0, "id": 1, "totalAmount": 1, "orderedAt": 1, "userId": 1}
        ).sort("orderedAt", 1).limit(20).to_list(20)

        # Get user names for these orders
        user_ids = list(set(o.get("userId") for o in raw_orders if o.get("userId")))
        users = await db.Users.find(
            {"id": {"$in": user_ids}},
            {"_id": 0, "id": 1, "name": 1}
        ).to_list(len(user_ids)) if user_ids else []
        user_map = {u["id"]: u.get("name", "Unknown") for u in users}

        for o in raw_orders:
            stuck_orders.append({
                "order_id": o["id"],
                "amount": o.get("totalAmount"),
                "ordered_at": o["orderedAt"].strftime("%Y-%m-%d") if o.get("orderedAt") else None,
                "customer": user_map.get(o.get("userId"), "Unknown")
            })

    return {
        "period_start": start.strftime("%Y-%m-%d"),
        "period_end": end.strftime("%Y-%m-%d"),
        "breakdown": breakdown,
        "stuck_processing_count": stuck_processing,
        "stuck_orders": stuck_orders,
    }