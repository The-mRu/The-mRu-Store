import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables (OPENAI_API_KEY)
load_dotenv()

# Initialize OpenAI Client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize MongoDB Client (Defaulting to localhost based on your handoff)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
mongo_client = AsyncIOMotorClient(MONGO_URI)

# Connect to your specific database
db = mongo_client.amazon_clone_db 

async def generate_embedding(text: str):
    """Sends text to OpenAI and returns the 1536-dimension math vector."""
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

async def backfill_products():
    print("🚀 Starting Vector Backfill...")
    
    # 1. Find ONLY the products that don't have an embedding yet
    cursor = db.Products.find({"embedding": {"$exists": False}}) 
    
    count = 0
    async for product in cursor:
        # 2. Extract the text safely (using .get() in case a field is missing)
        name = product.get("name", "Unknown Product")
        category = product.get("category", "Uncategorized")
        desc = product.get("description", "")
        
        # 3. Combine it into one highly-detailed string for the AI
        rich_text = f"Product: {name} | Category: {category} | Description: {desc}"
        print(f"Translating: {name}...")
        
        # 4. Get the math vector from OpenAI
        vector = await generate_embedding(rich_text)
        
        # 5. Save the vector back into the exact same MongoDB document
        await db.Products.update_one(
            {"_id": product["_id"]},
            {"$set": {"embedding": vector}}
        )
        count += 1
        
    print(f"✅ Backfill Complete! Successfully updated {count} products.")

if __name__ == "__main__":
    # Run the async loop
    asyncio.run(backfill_products())