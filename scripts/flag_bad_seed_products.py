# scripts/flag_bad_seed_products.py
import pymongo

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["amazon_clone_db"]

# Brands that plausibly belong in each category — extend as needed
VALID_BRANDS_BY_CATEGORY = {
    "cat_footwear": ["brand_nike", "brand_adidas", "brand_reebok", "brand_clarks", "brand_mru", None],
    "cat_computers": ["brand_dell", "brand_hp", "brand_lenovo", "brand_acer", "brand_msi", "brand_asus", None],
    "cat_mens_clothing": ["brand_carhartt", "brand_vince", "brand_hanes", "brand_thursday", "brand_levis", None],
    "cat_womens_clothing": ["brand_zara", "brand_allegra_k", "brand_evdexr", None],
    # extend for other categories as you audit them
}

flagged = []
for cat_id, valid_brands in VALID_BRANDS_BY_CATEGORY.items():
    bad = db.Products.find(
        {"categoryId": cat_id, "brandId": {"$nin": valid_brands}},
        {"name": 1, "brandId": 1}
    )
    for p in bad:
        flagged.append(p)
        print(f"MISMATCH: {p['name']!r} (brand: {p.get('brandId')}) in {cat_id}")

print(f"\nTotal flagged: {len(flagged)}")

# Mark them inactive rather than deleting outright — reversible
ids_to_hide = [p["_id"] for p in flagged]
if ids_to_hide:
    result = db.Products.update_many(
        {"_id": {"$in": ids_to_hide}},
        {"$set": {"status": "inactive"}}
    )
    print(f"Marked {result.modified_count} products as inactive.")