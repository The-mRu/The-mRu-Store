# testing/test_cart.py

import pytest
from httpx import AsyncClient, ASGITransport
from main_db_server import app


@pytest.mark.asyncio
async def test_full_cart_flow():
    """Add → View → Update → Remove → Verify empty"""
    user = "test_user_cart_flow"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Add product - using GET since that's what your API uses
        r = await client.get("/cart/manage", params={
            "action": "add",
            "product_id": "prod_auto_9",  # Using actual product from DB
            "quantity": 2,
            "user_id": user
        })
        assert r.status_code == 200
        assert r.json()["status"] == "added"

        # View cart — should have 1 item
        r = await client.get("/cart/manage", params={
            "action": "view",
            "user_id": user
        })
        assert r.status_code == 200
        data = r.json()
        
        # Check if response has items (could be dict with items or direct list)
        if isinstance(data, dict):
            assert "items" in data
            assert len(data["items"]) >= 1
            assert data.get("item_count", 0) >= 1
            assert data.get("total", 0) > 0
        else:
            # If it's a direct list of items
            assert len(data) >= 1

        # Remove product (quantity = 0)
        r = await client.get("/cart/manage", params={
            "action": "update",
            "product_id": "prod_auto_9",
            "quantity": 0,
            "user_id": user
        })
        assert r.status_code == 200

        # Verify empty
        r = await client.get("/cart/manage", params={
            "action": "view",
            "user_id": user
        })
        assert r.status_code == 200
        data = r.json()
        
        # Empty cart could be dict with empty items or empty list
        if isinstance(data, dict):
            # Check if it's a dict with items field
            if "items" in data:
                assert len(data["items"]) == 0
                # item_count and total might not exist for empty cart
                if "item_count" in data:
                    assert data["item_count"] == 0
                if "total" in data:
                    assert data["total"] == 0
            else:
                # Maybe it returns a dict with other structure
                assert len(data) == 0 or data == {}
        else:
            # Direct list
            assert len(data) == 0
            assert data == []


@pytest.mark.asyncio
async def test_cart_add_invalid_product():
    """Adding a non-existent product should fail"""
    user = "test_user_invalid"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/cart/manage", params={
            "action": "add",
            "product_id": "prod_fake_does_not_exist",
            "quantity": 1,
            "user_id": user
        })
        # Your API returns 404 for product not found
        assert r.status_code == 404
        # Optional: check error message
        assert "not found" in r.text.lower()


@pytest.mark.asyncio
async def test_cart_view_empty():
    """Viewing cart for a new user should return empty"""
    user = "test_user_empty_cart"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/cart/manage", params={
            "action": "view",
            "user_id": user
        })
        assert r.status_code == 200
        data = r.json()
        
        # Handle different response formats
        if isinstance(data, dict):
            # If it's a dict, it might be {"items": []}
            if "items" in data:
                assert len(data["items"]) == 0
            else:
                # Or just empty dict
                assert data == {} or len(data) == 0
            # Don't assert item_count if it doesn't exist
        else:
            # Direct list
            assert len(data) == 0


@pytest.mark.asyncio
async def test_cart_update_quantity():
    """Updating quantity should change the cart"""
    user = "test_user_qty_update"
    product_id = "prod_auto_9"  # Using actual product
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Add 1
        await client.get("/cart/manage", params={
            "action": "add", "product_id": product_id, "quantity": 1, "user_id": user
        })
        
        # Update to 5
        r = await client.get("/cart/manage", params={
            "action": "update", "product_id": product_id, "quantity": 5, "user_id": user
        })
        assert r.status_code == 200
        
        # Verify quantity
        r = await client.get("/cart/manage", params={
            "action": "view", "user_id": user
        })
        data = r.json()
        
        # Handle different response formats
        if isinstance(data, dict):
            # Get items from dict
            items = data.get("items", [])
            assert len(items) > 0
            # Find the product in items
            product = next((item for item in items if item["product_id"] == product_id), None)
            assert product is not None
            assert product["quantity"] == 5
            assert product["subtotal"] == 5 * product["price"]  # Verify subtotal
        else:
            # Direct list
            assert len(data) > 0
            product = next((item for item in data if item["product_id"] == product_id), None)
            assert product is not None
            assert product["quantity"] == 5
        
        # Clean up - set to 0
        await client.get("/cart/manage", params={
            "action": "update", "product_id": product_id, "quantity": 0, "user_id": user
        })


@pytest.mark.asyncio
async def test_cart_checkout_disabled():
    """Checkout should be disabled for chatbot"""
    user = "test_user_no_checkout"
    product_id = "prod_auto_9"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Add item first
        await client.get("/cart/manage", params={
            "action": "add", "product_id": product_id, "quantity": 1, "user_id": user
        })
        
        # Try checkout
        r = await client.get("/cart/manage", params={
            "action": "checkout", "user_id": user
        })
        # Should fail — checkout disabled
        assert r.status_code in (400, 404, 405)  # API returns 404 as endpoint doesn't exist
        
        # Clean up - remove item
        await client.get("/cart/manage", params={
            "action": "update", "product_id": product_id, "quantity": 0, "user_id": user
        })


@pytest.mark.asyncio
async def test_cart_multiple_products():
    """Test cart with multiple products from actual DB"""
    user = "test_user_multiple"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Add first product (using actual IDs from your response)
        await client.get("/cart/manage", params={
            "action": "add", 
            "product_id": "prod_custom_b4b432",  # iPhone 16
            "quantity": 2, 
            "user_id": user
        })
        
        # Add second product
        await client.get("/cart/manage", params={
            "action": "add", 
            "product_id": "prod_custom_81cd04",  # Levi's Jeans
            "quantity": 1, 
            "user_id": user
        })
        
        # View cart
        r = await client.get("/cart/manage", params={
            "action": "view", 
            "user_id": user
        })
        assert r.status_code == 200
        data = r.json()
        
        # Handle different response formats
        if isinstance(data, dict):
            # Check structure matches your API response
            assert "items" in data
            items = data["items"]
            assert len(items) == 2
            
            # Check optional fields if they exist
            if "total" in data:
                expected_total = sum(item["subtotal"] for item in items)
                assert data["total"] == expected_total
            if "item_count" in data:
                assert data["item_count"] == 2
        else:
            # Direct list
            assert len(data) == 2
            items = data
        
        # Verify each item has required fields
        for item in items:
            assert "product_id" in item
            assert "name" in item
            assert "price" in item
            assert "quantity" in item
            assert "subtotal" in item
            # Optional fields
            if "thumbnail" in item:
                assert isinstance(item["thumbnail"], str)
            if "in_stock" in item:
                assert isinstance(item["in_stock"], bool)
        
        # Clean up
        await client.get("/cart/manage", params={
            "action": "update", "product_id": "prod_custom_b4b432", "quantity": 0, "user_id": user
        })
        await client.get("/cart/manage", params={
            "action": "update", "product_id": "prod_custom_81cd04", "quantity": 0, "user_id": user
        })


@pytest.mark.asyncio
async def test_cart_with_real_db_product():
    """Test using product directly from DB"""
    user = "test_user_real_product"
    product_id = "prod_auto_9"  # Samsung Essential Monitor from your DB
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Add product
        r = await client.get("/cart/manage", params={
            "action": "add",
            "product_id": product_id,
            "quantity": 3,
            "user_id": user
        })
        assert r.status_code == 200
        
        # View and verify product details
        r = await client.get("/cart/manage", params={
            "action": "view",
            "user_id": user
        })
        data = r.json()
        
        # Handle different response formats
        if isinstance(data, dict):
            items = data.get("items", [])
        else:
            items = data
        
        # Find our product
        product = next((item for item in items if item["product_id"] == product_id), None)
        assert product is not None
        assert product["name"] == "Samsung Essential Monitor"  # Matches DB
        assert product["quantity"] == 3
        
        # Clean up
        await client.get("/cart/manage", params={
            "action": "update", "product_id": product_id, "quantity": 0, "user_id": user
        })


# Additional test to debug the actual response structure
@pytest.mark.asyncio
async def test_debug_cart_response():
    """Debug test to see what the API actually returns"""
    user = "test_debug_user"
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # View empty cart
        r = await client.get("/cart/manage", params={
            "action": "view",
            "user_id": user
        })
        print(f"\nStatus: {r.status_code}")
        print(f"Response type: {type(r.json())}")
        print(f"Response data: {r.json()}")
        assert r.status_code == 200