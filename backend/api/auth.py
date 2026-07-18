from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from backend.db.database import db
import uuid
import datetime

router = APIRouter()

# UPGRADE: Using Argon2id instead of bcrypt. No more 72-byte limits!
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

class UserRegister(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register_user(user: UserRegister):
    # Check if user already exists
    existing_user = await db.Users.find_one({"email": user.email.lower()})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Hash the password directly - Argon2 handles any length safely
    hashed_password = pwd_context.hash(user.password)
    
    new_user = {
        "id": str(uuid.uuid4()),
        "name": user.name,
        "email": user.email.lower(),
        "password": hashed_password,
        "created_at": datetime.datetime.utcnow()
    }
    
    await db.Users.insert_one(new_user)
    
    return {"id": new_user["id"], "name": new_user["name"], "email": new_user["email"]}

@router.post("/login")
async def login_user(user: UserLogin):
    # Find user
    db_user = await db.Users.find_one({"email": user.email.lower()})
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    # Verify password
    try:
        if not pwd_context.verify(user.password, db_user["password"]):
            raise HTTPException(status_code=400, detail="Invalid email or password")
    except UnknownHashError:
        # Still gracefully catches your old plain-text test accounts!
        raise HTTPException(status_code=400, detail="Legacy account detected. Please register a new account.")

    return {"id": db_user["id"], "name": db_user["name"], "email": db_user["email"]}