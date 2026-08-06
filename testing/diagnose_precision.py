# testing/diagnose_precision.py
import asyncio
from backend.api.search import search_products_core

DIAGNOSE_QUERIES = ["Nike shoes", "iPhone", "men's t-shirt", "Dell laptop"]

async def diagnose():
    for query in DIAGNOSE_QUERIES:
        result = await search_products_core(q=query)
        products = result.get("products", [])
        print(f"\n{'='*70}")
        print(f"QUERY: '{query}'  —  {len(products)} returned")
        print(f"{'='*70}")
        for i, p in enumerate(products):
            name = str(p.get("name") or "?")
            brand = str(p.get("brandId") or "-")
            cat = str(p.get("categoryId") or "-")
            score = str(p.get("score") or p.get("rrf_score") or p.get("_score") or "?")
            print(f"  {i+1:>2}. score={score:<8} brand={brand:<15} cat={cat:<20} {name}")

if __name__ == "__main__":
    asyncio.run(diagnose())