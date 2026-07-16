# from fastapi import APIRouter
# from backend.db.database import db

# router = APIRouter()

# @router.get("/")
# def get_all_users():
#     users = list(db.Users.find({}, {"_id": 0}))
#     return users


from fastapi import APIRouter
from backend.db.database import db

router = APIRouter()

@router.get("/")
async def get_all_users():
    # 1. Added 'async', 2. Added 'await', 3. Swapped list() for .to_list()
    users = await db.Users.find({}, {"_id": 0}).to_list(length=100)
    return users