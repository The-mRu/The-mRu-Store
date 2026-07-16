# from fastapi import APIRouter, HTTPException
# from backend.db.database import db

# router = APIRouter()

# @router.get("/product/{product_id}")
# def get_reviews_for_product(product_id: str):
#     reviews = list(db.Reviews.find({"productId": product_id}, {"_id": 0}))
#     if not reviews:
#         raise HTTPException(status_code=404, detail="No reviews found")
#     return reviews

# #get all reviews
# @router.get("/")
# def get_all_reviews():
#     reviews = list(db.Reviews.find({}, {"_id": 0}))
#     return reviews


from fastapi import APIRouter, HTTPException
from backend.db.database import db

router = APIRouter()

@router.get("/product/{product_id}")
async def get_reviews_for_product(product_id: str):
    # 1. Added 'async', 2. Added 'await', 3. Swapped list() for .to_list()
    reviews = await db.Reviews.find({"productId": product_id}, {"_id": 0}).to_list(length=100)
    
    if not reviews:
        raise HTTPException(status_code=404, detail="No reviews found for this product")
    return reviews

# Get all reviews
@router.get("/")
async def get_all_reviews():
    # 1. Added 'async', 2. Added 'await', 3. Swapped list() for .to_list()
    reviews = await db.Reviews.find({}, {"_id": 0}).to_list(length=100)
    return reviews