from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from backend.db.database import db
import uuid
from datetime import datetime

router = APIRouter()

# --- PYDANTIC MODELS (Defines what JSON FastAPI expects) ---
class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    role: str = "customer"
    isVerified: bool = False
    isActive: bool = True

class UserLogin(BaseModel):
    email: str
    password: str

# --- ROUTES ---

@router.get("/")
async def get_all_users():
    # 1. Added 'async', 2. Added 'await', 3. Swapped list() for .to_list()
    users = await db.Users.find({}, {"_id": 0}).to_list(length=100)
    return users

@router.post("/register")
async def register_user(user: UserRegister):
    """Creates a new user in MongoDB."""
    # 1. Check if the email is already in the database
    existing_user = await db.Users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Prepare the new user document
    new_user = user.dict()
    new_user["id"] = str(uuid.uuid4()) # Generate a unique string ID
    new_user["createdAt"] = datetime.utcnow()

    # 3. Insert into MongoDB
    await db.Users.insert_one(new_user.copy())

    # 4. Return the user info to Django (so it can save the session)
    return {"id": new_user["id"], "name": new_user["name"], "email": new_user["email"]}

@router.post("/login")
async def login_user(credentials: UserLogin):
    """Verifies a user's credentials against MongoDB."""
    # 1. Look up the user by email
    user = await db.Users.find_one({"email": credentials.email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Check the password
    # Note: In a production app, you will want to hash this using passlib/bcrypt!
    if user["password"] != credentials.password:
        raise HTTPException(status_code=401, detail="Incorrect password")

    # 3. Return the user info to Django
    return {"id": user["id"], "name": user["name"], "email": user["email"]}