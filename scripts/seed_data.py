import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "amazon_clone_db"

async def seed_if_empty():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    # Check if products already exist
    product_count = await db.Products.count_documents({})
    
    if product_count > 0:
        print(f"✅ Database already has {product_count} products. Skipping full seed.")
        print("You can still run backfill_vectors.py if embeddings are missing.")
        client.close()
        return

    # Only seed if empty
    print("Database appears empty. Seeding sample data...")

    categories = [ ... ]   # (same as before)
    brands = [ ... ]
    products = [ ... ]

    await db.Categories.insert_many(categories)
    await db.Brands.insert_many(brands)
    await db.Products.insert_many(products)

    print(f"✅ Seeded {len(categories)} categories, {len(brands)} brands, and {len(products)} products.")

    client.close()

if __name__ == "__main__":
    asyncio.run(seed_if_empty())