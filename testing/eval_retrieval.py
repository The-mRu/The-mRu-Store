# testing/eval_retrieval.py
import asyncio
from backend.api.search import search_products_core

EVAL_QUERIES = [
    {
        "query": "women's dress",
        "relevant_categories": ["cat_womens_clothing"],
        "relevant_keywords": ["dress", "women"]
    },
    {
        "query": "Dell laptop",
        "relevant_brands": ["brand_dell"],
        "relevant_categories": ["cat_computers"],
        "relevant_keywords": ["dell", "laptop"]
    },
    {
        "query": "Nike shoes",
        "relevant_brands": ["brand_nike"],
        "relevant_categories": ["cat_footwear"],
        "relevant_keywords": ["nike", "shoe", "sneaker"]
    },
    {
        "query": "iPhone",
        "relevant_brands": ["brand_apple"],
        "relevant_keywords": ["iphone", "apple"]
    },
    {
        "query": "gaming laptop",
        "relevant_categories": ["cat_computers", "cat_gaming_laptops"],
        "relevant_keywords": ["gaming", "laptop"]
    },
    {
        "query": "saree",
        "relevant_keywords": ["saree", "sari"]
    },
    {
        "query": "wireless headphones",
        "relevant_categories": ["cat_audio"],
        "relevant_keywords": ["headphone", "wireless", "earbud", "audio"]
    },
    {
        "query": "men's t-shirt",
        "relevant_categories": ["cat_mens_clothing"],
        "relevant_keywords": ["men", "t-shirt", "shirt"]
    },
]


async def compute_retrieval_precision():
    results_summary = []
    
    for case in EVAL_QUERIES:
        result = await search_products_core(q=case["query"])
        products = result.get("products", [])

        relevant = 0
        for p in products:
            matches_category = p.get("categoryId") in case.get("relevant_categories", [])
            matches_brand = p.get("brandId") in case.get("relevant_brands", [])
            matches_keyword = any(
                kw.lower() in p.get("name", "").lower()
                for kw in case.get("relevant_keywords", [])
            )
            if matches_category or matches_brand or matches_keyword:
                relevant += 1

        precision = round(relevant / len(products), 2) if products else 0
        results_summary.append({
            "query": case["query"],
            "returned": len(products),
            "relevant": relevant,
            "precision": precision,
        })

    avg_precision = round(
        sum(r["precision"] for r in results_summary) / len(results_summary), 2
    )

    print(f"\n{'='*65}")
    print(f"  RETRIEVAL PRECISION — {len(EVAL_QUERIES)} Test Queries")
    print(f"{'='*65}")
    print(f"  {'Query':<25} {'Returned':>8} {'Relevant':>8} {'Precision':>10}")
    print(f"  {'-'*51}")
    for r in results_summary:
        print(f"  {r['query']:<25} {r['returned']:>8} {r['relevant']:>8} {r['precision']:>9.0%}")
    print(f"  {'-'*51}")
    print(f"  {'AVERAGE PRECISION':<25} {avg_precision:>27.0%}")
    print(f"{'='*65}")

    return {"average_precision": avg_precision, "per_query": results_summary}


if __name__ == "__main__":
    asyncio.run(compute_retrieval_precision())
    
### python -m testing.eval_retrieval