import pymongo

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["amazon_clone_db"]

# New brands that need to be inserted (don't exist in Brands at all yet)
NEW_BRANDS = [
    {"id": "brand_dell", "name": "Dell", "slug": "dell"},
    {"id": "brand_hp", "name": "HP", "slug": "hp"},
    {"id": "brand_lenovo", "name": "Lenovo", "slug": "lenovo"},
    {"id": "brand_acer", "name": "Acer", "slug": "acer"},
    {"id": "brand_msi", "name": "MSI", "slug": "msi"},
    {"id": "brand_logitech", "name": "Logitech", "slug": "logitech"},
    {"id": "brand_reebok", "name": "Reebok", "slug": "reebok"},
    {"id": "brand_carhartt", "name": "Carhartt", "slug": "carhartt"},
    {"id": "brand_vince", "name": "Vince", "slug": "vince"},
    {"id": "brand_clarks", "name": "Clarks", "slug": "clarks"},
    {"id": "brand_hanes", "name": "Hanes", "slug": "hanes"},
    {"id": "brand_allegra_k", "name": "Allegra K", "slug": "allegra-k"},
    {"id": "brand_evdexr", "name": "Evdexr", "slug": "evdexr"},
    {"id": "brand_thursday", "name": "Thursday", "slug": "thursday"},
]

for brand in NEW_BRANDS:
    db.Brands.update_one({"id": brand["id"]}, {"$setOnInsert": brand}, upsert=True)
print(f"Ensured {len(NEW_BRANDS)} brand documents exist.")

# keyword (checked case-insensitively against product name) -> brandId
# Order matters: more specific keywords first (e.g. "evi's" before generic fallback)
KEYWORD_TO_BRAND = [
    ("dell", "brand_dell"),
    ("hp ", "brand_hp"), ("hp spectre", "brand_hp"), ("hp envy", "brand_hp"), ("hp monitor", "brand_hp"),
    ("lenovo", "brand_lenovo"),
    ("acer", "brand_acer"),
    ("msi", "brand_msi"),
    ("logitech", "brand_logitech"),
    ("asus", "brand_asus"),
    ("samsung", "brand_samsung"),
    ("iphone", "brand_apple"),
    ("nike", "brand_nike"),
    ("adidas", "brand_adidas"),
    ("reebok", "brand_reebok"),
    ("carhartt", "brand_carhartt"),
    ("vince", "brand_vince"),
    ("clarks", "brand_clarks"),
    ("hanes", "brand_hanes"),
    ("allegra k", "brand_allegra_k"),
    ("evdexr", "brand_evdexr"),
    ("thursday", "brand_thursday"),
    ("evi's 501", "brand_levis"),   # typo for Levi's
    ("sony", "brand_sony"),
]

valid_brand_ids = {b["id"] for b in db.Brands.find({}, {"id": 1})}
broken = list(db.Products.find({"brandId": {"$nin": list(valid_brand_ids)}}, {"name": 1}))

matched, unbranded = 0, 0
for product in broken:
    name_lower = product["name"].lower()
    resolved_brand = None
    for keyword, brand_id in KEYWORD_TO_BRAND:
        if keyword in name_lower:
            resolved_brand = brand_id
            break

    db.Products.update_one(
        {"_id": product["_id"]},
        {"$set": {"brandId": resolved_brand}}   # None if no keyword matched — explicit "no brand"
    )
    if resolved_brand:
        matched += 1
        print(f"  {product['name']!r} -> {resolved_brand}")
    else:
        unbranded += 1
        print(f"  {product['name']!r} -> no brand (generic)")

print(f"\nDone. {matched} matched to a brand, {unbranded} set to unbranded (brandId: null).")