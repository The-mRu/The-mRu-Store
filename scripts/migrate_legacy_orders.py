# scripts/migrate_legacy_orders.py
import pymongo
import uuid
from datetime import datetime

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["amazon_clone_db"]

def migrate_legacy_orders():
    legacy_orders = list(db.Orders.find({"order_id": {"$exists": True}}))
    print(f"Found {len(legacy_orders)} legacy-shape orders to migrate.")

    order_seq_start = db.Orders.count_documents({"id": {"$exists": True}}) + 1

    for i, order in enumerate(legacy_orders):
        seq = order_seq_start + i
        new_id = f"ord_{seq:04d}"
        new_order_number = f"ORD-2026-{seq:05d}"

        total = order.get("total", 0.0)

        # These orders were placed with no real Address/Payment records —
        # create minimal placeholder records so addressId/paymentId stay valid references
        # rather than dangling/fabricated strings.
        address_id = f"addr_legacy_{seq}"
        db.Addresses.update_one(
            {"id": address_id},
            {"$setOnInsert": {
                "id": address_id,
                "userId": order.get("userId"),
                "fullName": "Legacy Order — Address Unknown",
                "phone": "",
                "country": "",
                "city": "",
                "area": "",
                "street": order.get("shipping", {}).get("address", "Unknown"),
                "postalCode": "",
                "isDefault": False,
                "createdAt": order.get("created_at", datetime.utcnow()),
            }},
            upsert=True
        )

        payment_id = f"pay_legacy_{seq}"
        db.Payments.update_one(
            {"id": payment_id},
            {"$setOnInsert": {
                "id": payment_id,
                "orderId": new_id,
                "paymentMethod": "Unknown (Legacy)",
                "transactionId": f"TXN-LEGACY-{uuid.uuid4().hex[:8].upper()}",
                "amount": total,
                "currency": "USD",
                "status": "completed",
                "paidAt": order.get("created_at", datetime.utcnow()),
            }},
            upsert=True
        )

        new_order_data = {
            "id": new_id,
            "orderNumber": new_order_number,
            "userId": order.get("userId"),
            "addressId": address_id,
            "paymentId": payment_id,
            "items": order.get("items", []),
            "subtotal": total,
            "discount": 0.0,
            "shippingFee": 0.0,
            "totalAmount": total,
            "status": order.get("status", "Processing"),
            "paymentStatus": "paid",
            "orderedAt": order.get("created_at", datetime.utcnow()),
            "deliveredAt": None,
        }

        db.Orders.update_one(
            {"_id": order["_id"]},
            {"$set": new_order_data, "$unset": {"order_id": "", "total": "", "created_at": "", "shipping": ""}}
        )
        print(f"Migrated {order.get('order_id')} -> {new_id}")

    print(f"Done. Migrated {len(legacy_orders)} orders.")


if __name__ == "__main__":
    migrate_legacy_orders()