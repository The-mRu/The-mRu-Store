# scripts/flag_bad_seed_products.py
import pymongo

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["amazon_clone_db"]

# Brands that plausibly belong in each category — extend as you audit more categories
VALID_BRANDS_BY_CATEGORY = {
    "cat_computers": ["brand_dell", "brand_hp", "brand_lenovo", "brand_acer", "brand_msi", "brand_asus", None],
    "cat_gaming_laptops": ["brand_dell", "brand_hp", "brand_lenovo", "brand_acer", "brand_msi", "brand_asus", None],
    "cat_monitors": ["brand_dell", "brand_hp", "brand_asus", "brand_samsung", "brand_sony", None],
    "cat_mobile": ["brand_apple", "brand_samsung", "brand_sony", None],
    "cat_smartphones": ["brand_apple", "brand_samsung", "brand_sony", None],
    "cat_powerbanks": ["brand_anker", None],
    "cat_audio": ["brand_sony", "brand_logitech", "brand_apple", None],
    "cat_footwear": ["brand_nike", "brand_adidas", "brand_reebok", "brand_clarks", "brand_mru", None],
    "cat_mens_clothing": ["brand_carhartt", "brand_vince", "brand_hanes", "brand_thursday", "brand_levis", None],
    "cat_mens_tshirts": ["brand_hanes", "brand_carhartt", "brand_levis", None],
    "cat_mens_jeans": ["brand_levis", "brand_carhartt", None],
    "cat_womens_clothing": ["brand_zara", "brand_allegra_k", "brand_evdexr", None],
    "cat_appliances": ["brand_dyson", "brand_philips", "brand_ikea", None],
    "cat_furniture": ["brand_ikea", None],
    "cat_skincare": ["brand_loreal", "brand_cerave", "brand_mac", None],
    "cat_fragrance": ["brand_loreal", "brand_cerave", "brand_mac", None],
    "cat_coffee_makers": ["brand_philips", "brand_dyson", "brand_ikea", None],
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

ids_to_hide = [p["_id"] for p in flagged]
if ids_to_hide:
    result = db.Products.update_many(
        {"_id": {"$in": ids_to_hide}},
        {"$set": {"status": "inactive"}}
    )
    print(f"Marked {result.modified_count} products as inactive.")