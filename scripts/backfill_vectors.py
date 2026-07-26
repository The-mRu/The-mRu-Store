# scripts/backfill_normalized_search.py
import os
import re
import asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client.amazon_clone_db


def normalize_text(s: str) -> str:
    """Strip everything except letters/digits, lowercased.
    't-shirt', 'tshirt', 't shirt' → 'tshirt'
    """
    return re.sub(r'[^a-z0-9]', '', s.lower())


async def backfill_normalized_search():
    print("🚀 Starting searchNormalized backfill...")

    # Only process products that don't have the field yet
    cursor = db.Products.find({"searchNormalized": {"$exists": False}})

    count = 0
    async for product in cursor:
        name = product.get("name", "")
        short = product.get("shortDescription", "")
        desc = product.get("description", "")
        full_text = f"{name} {short} {desc}"
        normalized = normalize_text(full_text)

        print(f"Updating: {name}...")
        await db.Products.update_one(
            {"_id": product["_id"]},
            {"$set": {"searchNormalized": normalized}}
        )
        count += 1

    print(f"✅ Backfill complete! Updated {count} products.")


if __name__ == "__main__":
    asyncio.run(backfill_normalized_search())
    
### python scripts/backfill_normalized_search.py