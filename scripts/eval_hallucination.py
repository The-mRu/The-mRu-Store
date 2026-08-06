# scripts/eval_hallucination.py
import asyncio
import re
import json
from datetime import datetime, timedelta, UTC
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client.amazon_clone_db

PRICE_RE = r'\$\d[\d,]*(?:\.\d{2})?'


def normalize_price(p: str) -> str:
    """Normalize price strings for comparison: $1,200.00 → 1200"""
    p = p.replace('$', '').replace(',', '')
    if '.' in p:
        p = p.rstrip('0').rstrip('.')
    return p


async def compute_hallucination_rate(days: int = 7):
    since = datetime.now(UTC) - timedelta(days=days)

    tool_logs = await db.AgentLogs.find({
        "event_type": "tool_call",
        "timestamp": {"$gte": since}
    }).to_list(10000)

    grounded_ids = set()
    grounded_prices = set()

    for log in tool_logs:
        snippet = log.get("response_snippet", "")

        # Product IDs
        grounded_ids.update(re.findall(r'\bprod_[a-zA-Z0-9_]+\b', snippet))

        # Prices with $ prefix
        for p in re.findall(PRICE_RE, snippet):
            grounded_prices.add(normalize_price(p))

        # Bare numbers from JSON fields (price, subtotal, total, total_amount)
        for p in re.findall(r"'(?:price|subtotal|total|total_amount)':\s*([\d.]+)", snippet):
            grounded_prices.add(normalize_price(p))

        # Also extract order IDs from order-related tool responses
        if log.get("tool_name") in ("get_user_orders", "check_order_status", "get_order_items"):
            grounded_ids.update(re.findall(r'\bord_[a-zA-Z0-9_]+\b', snippet))

        # Also extract ticket IDs from ticket-related tool responses
        if log.get("tool_name") in ("get_user_tickets", "check_ticket_status", "create_support_ticket"):
            grounded_ids.update(re.findall(r'\btick_[a-zA-Z0-9_]+\b', snippet))

    responses = await db.AgentLogs.find({
        "event_type": "final_response",
        "timestamp": {"$gte": since}
    }).to_list(1000)

    flagged = []
    for log in responses:
        text = log.get("final_text", "")
        claimed_ids = re.findall(r'\b(?:prod|ord|tick)_[a-zA-Z0-9_]+\b', text)
        claimed_prices = [normalize_price(p) for p in re.findall(PRICE_RE, text)]

        unsupported_ids = [i for i in claimed_ids if i not in grounded_ids]
        unsupported_prices = [p for p in claimed_prices if p not in grounded_prices]

        if unsupported_ids or unsupported_prices:
            flagged.append({
                "user_id": log.get("user_id"),
                "message": log.get("user_message", "")[:150],
                "response_snippet": text[:300],
                "unsupported_ids": unsupported_ids,
                "unsupported_prices": unsupported_prices,
                "timestamp": log.get("timestamp"),
            })

    total = len(responses)
    flagged_count = len(flagged)
    rate = round(flagged_count / total * 100, 1) if total else 0

    print(f"\n{'='*60}")
    print(f"  HALLUCINATION SCAN — Last {days} Days")
    print(f"{'='*60}")
    print(f"  Total responses:        {total}")
    print(f"  Flagged for review:     {flagged_count}")
    print(f"  Flag rate:              {rate}%")
    print(f"  NOTE: Flags are candidates for manual review,")
    print(f"        not confirmed hallucinations.")
    print(f"{'='*60}")

    if flagged:
        print(f"\n  Flagged Responses:")
        for i, f in enumerate(flagged, 1):
            print(f"\n  #{i} | User: {f['user_id']}")
            print(f"  Message: {f['message']}")
            print(f"  Response: {f['response_snippet']}")
            print(f"  Unsupported IDs:    {f['unsupported_ids'] or 'None'}")
            print(f"  Unsupported Prices: {f['unsupported_prices'] or 'None'}")
    else:
        print(f"\n  ✅ No flagged responses. All claims appear grounded.")

    return {
        "total": total,
        "flagged": flagged_count,
        "flag_rate": rate,
        "details": flagged,
        "note": "Heuristic only — manual review required to confirm hallucinations"
    }


if __name__ == "__main__":
    asyncio.run(compute_hallucination_rate())
