# scripts/backfill_vectors.py
import argparse
import pymongo
from sentence_transformers import SentenceTransformer

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["amazon_clone_db"]

print("Loading Embedding Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

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

        brand_name = None
        if product.get("brandId"):
            brand_doc = db.Brands.find_one({"id": product["brandId"]})
            brand_name = brand_doc["name"] if brand_doc else None
        brand_str = f" | brand: {brand_name}" if brand_name else ""

        search_text = (
            f"{name} | category: {cat_name} | for: {gender}{brand_str} | "
            f"tags: {tags} | {desc}"
        )
        embedding = model.encode(search_text).tolist()

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