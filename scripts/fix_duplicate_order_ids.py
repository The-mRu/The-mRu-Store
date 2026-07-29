# scripts/fix_duplicate_order_ids.py
import pymongo, uuid

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["amazon_clone_db"]

pipeline = [
    {"$group": {"_id": "$id", "count": {"$sum": 1}, "docs": {"$push": "$_id"}}},
    {"$match": {"count": {"$gt": 1}}}
]

for group in db.Orders.aggregate(pipeline):
    mongo_ids = group["docs"]
    # Keep the first one as-is, reassign the rest
    for mongo_id in mongo_ids[1:]:
        new_id = f"ord_{uuid.uuid4().hex[:8]}"
        db.Orders.update_one({"_id": mongo_id}, {"$set": {"id": new_id}})
        print(f"Reassigned {mongo_id} -> {new_id}")

print("Done.")