# from fastapi import APIRouter, HTTPException
# from backend.db.database import db

# router = APIRouter()

# @router.get("/")
# def get_all_orders():
#     orders = list(db.Orders.find({}, {"_id": 0}))
#     return orders

# @router.get("/{order_id}/status")
# def get_order_status(order_id: str):
#     order = db.Orders.find_one({"id": order_id}, {"_id": 0, "status": 1})
#     if not order:
#         raise HTTPException(status_code=404, detail="Order not found")
#     return order

# @router.get("/user/{user_id}")
# def get_orders_by_user(user_id: str):
#     orders = list(db.Orders.find({"userId": user_id}, {"_id": 0}))
#     if not orders:
#         raise HTTPException(status_code=404, detail="No orders found for this user")
#     return orders


from fastapi import APIRouter, HTTPException
from backend.db.database import db

router = APIRouter()

@router.get("/")
async def get_all_orders():
    orders = await db.Orders.find({}, {"_id": 0}).to_list(length=100)
    return orders

@router.get("/{order_id}/status")
async def get_order_status(order_id: str):

    order = await db.Orders.find_one({"id": order_id}, {"_id": 0, "status": 1})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.get("/user/{user_id}")
async def get_user_orders(user_id: str):
    orders = await db.Orders.find({"userId": user_id}, {"_id": 0}).to_list(length=100)
    
    if not orders:
        raise HTTPException(status_code=404, detail="No orders found for this user")
        
    return orders