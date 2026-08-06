# scripts/eval_tool_success.py
import asyncio
from datetime import datetime, timedelta, UTC
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client.amazon_clone_db


async def compute_tool_success_rate(days: int = 7):
    """Calculate success rate per tool from AgentLogs."""
    since = datetime.now(UTC) - timedelta(days=days)
    
    logs = await db.AgentLogs.find({
        "event_type": "tool_call",
        "timestamp": {"$gte": since}
    }).to_list(10000)

    by_tool = {}
    for log in logs:
        name = log["tool_name"]
        if name not in by_tool:
            by_tool[name] = {"total": 0, "success": 0}
        by_tool[name]["total"] += 1
        if log["success"]:
            by_tool[name]["success"] += 1

    print(f"\n📊 Tool Success Rate (last {days} days)")
    print("-" * 50)
    print(f"{'Tool':<35} {'Success':>8} {'Total':>6}")
    print("-" * 50)

    for name, stats in sorted(by_tool.items()):
        rate = round(stats["success"] / stats["total"] * 100, 1)
        print(f"{name:<35} {rate:>7}% {stats['total']:>6}")

    print("-" * 50)
    
    # Flag tools with < 90% success
    print("\n⚠️  Tools needing attention (< 90% success):")
    for name, stats in by_tool.items():
        rate = stats["success"] / stats["total"] * 100
        if rate < 90:
            print(f"  {name}: {round(rate, 1)}% ({stats['success']}/{stats['total']})")

    return by_tool


if __name__ == "__main__":
    asyncio.run(compute_tool_success_rate())