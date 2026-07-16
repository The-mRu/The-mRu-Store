# import os
# from motor.motor_asyncio import AsyncIOMotorClient
# from dotenv import load_dotenv

# load_dotenv()

# MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
# client = AsyncIOMotorClient(MONGO_URI)

# db = client["amazon_clone_db"]



# from pymongo import MongoClient

# client = MongoClient("mongodb://localhost:27017")

# db = client["amazon_clone_db"]


from motor.motor_asyncio import AsyncIOMotorClient

# Create async MongoDB client
client = AsyncIOMotorClient("mongodb://localhost:27017")

# Select your database
db = client["amazon_clone_db"]
