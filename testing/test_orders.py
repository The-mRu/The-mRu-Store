# testing/test_orders.py
import pytest
from backend.api.orders import verify_order_for_ai, get_user_orders
from fastapi import HTTPException

@pytest.mark.asyncio
async def test_verify_real_order():
    result = await verify_order_for_ai("ord_0001", "user_1")
    assert result["valid"] is True

@pytest.mark.asyncio
async def test_verify_order_wrong_user_blocked():
    with pytest.raises(HTTPException) as exc:
        await verify_order_for_ai("ord_0001", "user_2")
    assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_get_user_orders_returns_real_data():
    orders = await get_user_orders("user_1")
    assert len(orders) > 0
    assert all(o["userId"] == "user_1" for o in orders)
        
### pytest testing/test_orders.py -v