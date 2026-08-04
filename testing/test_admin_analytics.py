# tests/test_admin_analytics.py
import pytest
from httpx import AsyncClient, ASGITransport
from main_db_server import app   
from backend.db.database import db
from datetime import UTC, datetime, timedelta


@pytest.mark.asyncio
async def test_tickets_summary_has_user_info():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/tickets-summary")
        assert response.status_code == 200
        data = response.json()
        
        assert "has_open_tickets" in data
        assert "has_urgent_tickets" in data
        assert "has_unassigned_tickets" in data
        
        if data["urgent_tickets"]:
            ticket = data["urgent_tickets"][0]
            assert "user_name" in ticket
            assert "user_email" in ticket


@pytest.mark.asyncio
async def test_tickets_summary_counts_match_db():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/tickets-summary")
        data = response.json()
        
        db_open = await db.SupportTickets.count_documents({"status": {"$in": ["open", "under review"]}})
        db_urgent = await db.SupportTickets.count_documents({"status": {"$in": ["open", "under review"]}, "priority": "urgent"})
        
        assert data["total_open_tickets"] == db_open
        assert data["total_urgent_tickets"] == db_urgent


@pytest.mark.asyncio
async def test_order_status_breakdown_returns_stuck_orders():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/order-status-breakdown")
        assert response.status_code == 200
        data = response.json()
        
        assert "breakdown" in data
        assert "stuck_processing_count" in data
        assert "stuck_orders" in data
        
        if data["stuck_orders"]:
            order = data["stuck_orders"][0]
            assert "order_id" in order
            assert "amount" in order
            assert "customer" in order


@pytest.mark.asyncio
async def test_order_status_breakdown_with_custom_date():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/order-status-breakdown?start_date=2026-07-01&end_date=2026-07-31")
        assert response.status_code == 200
        data = response.json()
        assert data["period_start"] == "2026-07-01"


@pytest.mark.asyncio
async def test_order_status_breakdown_counts_match_db():
    now = datetime.now(UTC)
    start = now - timedelta(days=7)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/order-status-breakdown")
        data = response.json()
        
        db_total = await db.Orders.count_documents({"orderedAt": {"$gte": start, "$lt": now}})
        api_total = sum(data["breakdown"].values())
        
        assert api_total == db_total