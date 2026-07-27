# testing/test_search.py
import sys
import os
import pytest
from backend.api.products import resolve_category, list_brands
from backend.api.search import search_products_core
sys.path.insert(0, os.path.dirname(__file__))


@pytest.mark.asyncio
async def test_gender_inference():
    result = await search_products_core(q="dress", category="womens-clothing", gender="women")
    assert all(p.get("gender") in ["women", "unisex"] for p in result["products"])
    
@pytest.mark.asyncio
async def test_no_inactive_products_in_search():
    result = await search_products_core(q="footwear")
    assert all(p.get("status", "active") == "active" for p in result["products"])

@pytest.mark.asyncio
async def test_price_filter():
    result = await search_products_core(q="laptop", max_price=60000)
    assert all(p["price"] <= 60000 for p in result["products"])

@pytest.mark.asyncio
async def test_category_resolution():
    cat_id, cat_name = await resolve_category("womens-clothing")
    assert cat_id == "cat_womens_clothing"
    assert cat_name == "Women's Clothing"


@pytest.mark.asyncio
async def test_category_resolution_unknown_slug():
    cat_id, cat_name = await resolve_category("not-a-real-category")
    assert cat_id is None


@pytest.mark.asyncio
async def test_brand_resolution_no_hallucination():
    brands = await list_brands(category="footwear")
    assert "Puma" not in brands
    assert "New Balance" not in brands
    assert "Nike" in brands  
    
    
    
@pytest.mark.asyncio
async def test_price_filter():
    result = await search_products_core(q="laptop", max_price=60000)
    assert all(p["price"] <= 60000 for p in result["products"])

###    pytest testing/test_search.py -v 