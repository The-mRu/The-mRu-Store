# scripts/backfill_vectors.py
import argparse
import os
import pymongo
from openai import OpenAI

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["amazon_clone_db"]

api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_ADMIN_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is missing. Set it before running this script.")

client_openai = OpenAI(api_key=api_key)
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")


def build_search_text(name, cat_name, gender, brand_name, warranty, rating, tags, desc):
    gender_str = gender or "unisex"
    brand_str = f" | brand: {brand_name}" if brand_name else ""
    warranty_str = f" | warranty: {warranty}" if warranty and warranty != "No Warranty" else ""
    rating_str = f" | rating: {rating}" if rating and rating > 0 else ""
    return (
        f"{name} | category: {cat_name} | for: {gender_str}{brand_str}{warranty_str}{rating_str} | "
        f"tags: {tags} | {desc}"
    )


def backfill_products(force=False):
    query = {} if force else {
        "$or": [
            {"searchText": {"$exists": False}},
            {"embedding": {"$exists": False}},
        ]
    }
    cursor = db.Products.find(query)
    count = 0

    for product in cursor:
        name = product.get("name", "")
        cat_name = product.get("category", "")
        gender = product.get("gender") or "unisex"
        desc = product.get("shortDescription") or product.get("description", "")
        tags = ", ".join(product.get("tags", []))
        warranty = product.get("warranty")
        rating = product.get("rating")

        brand_name = None
        if product.get("brandId"):
            brand_doc = db.Brands.find_one({"id": product["brandId"]})
            brand_name = brand_doc["name"] if brand_doc else None

        search_text = build_search_text(name, cat_name, gender, brand_name, warranty, rating, tags, desc)
        embedding = client_openai.embeddings.create(model=EMBEDDING_MODEL_NAME, input=search_text).data[0].embedding

        db.Products.update_one(
            {"_id": product["_id"]},
            {"$set": {"searchText": search_text, "embedding": embedding}}
        )
        print(f"Updated vectors for: {name}")
        count += 1

    print(f"Processed {count} product(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate for ALL products, even ones already indexed.")
    args = parser.parse_args()

    backfill_products(force=args.force)
    db.Products.create_index([("searchText", "text")])
    db.Products.create_index([("categoryId", 1), ("gender", 1), ("price", 1)])
    print("Done. Text and filter indexes ensured.")
    
### python scripts/backfill_vectors.py
### python scripts/backfill_vectors.py --force