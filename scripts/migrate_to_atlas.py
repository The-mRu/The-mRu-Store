# scripts/migrate_to_atlas.py
 
import certifi
from pymongo import MongoClient


# Source: your local DB
local = MongoClient("mongodb://localhost:27017")
local_db = local["amazon_clone_db"]

# Target: your Atlas DB
ATLAS_URI = "mongodb+srv://fsrrayhan_db_user:1K4VAjaBLS13DjVo@cluster0.obiwgd4.mongodb.net/"
atlas = MongoClient(ATLAS_URI, tlsCAFile=certifi.where())

atlas_db = atlas["amazon_clone_db"]

collections = local_db.list_collection_names()

for coll_name in collections:
    print(f"Migrating {coll_name}...")
    docs = list(local_db[coll_name].find())

    if docs:
        atlas_db[coll_name].delete_many({})
        atlas_db[coll_name].insert_many(docs)
        print(f"  → {len(docs)} documents copied")
    else:
        print(f"  → Empty collection, skipped")

print("\n✅ Migration complete!")
print("Check: https://cloud.mongodb.com → Browse Collections")