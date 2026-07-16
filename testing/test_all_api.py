import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

# Ensure project root is importable when running tests from the testing folder.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from main_db_server import app
from backend.api import analytics, categories, chat, inventory, orders, products, reviews, search, support_tickets, users


class FakeCursor:
    def __init__(self, data):
        self._data = data

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self._data = self._data[:n]
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self._data)
        return list(self._data)[:length]


class FakeCollection:
    def __init__(self, rows=None, find_one_fn=None, count=0):
        self.rows = rows or []
        self._find_one_fn = find_one_fn
        self._count = count

    def find(self, *_args, **_kwargs):
        return FakeCursor(self.rows)

    async def find_one(self, query, *_args, **_kwargs):
        if self._find_one_fn:
            return self._find_one_fn(query)
        return None

    async def count_documents(self, _query):
        return self._count

    def aggregate(self, _pipeline):
        return FakeCursor([{"totalSales": 999}])

    async def insert_one(self, _doc):
        return SimpleNamespace(inserted_id="ticket_123")


@pytest.fixture
def client(monkeypatch):
    fake_db = SimpleNamespace(
        Products=FakeCollection(
            rows=[{"id": "prod_001", "name": "Mouse", "stock": 3, "sales": 50}],
            find_one_fn=lambda q: {"id": "prod_001", "name": "Mouse"}
            if q.get("id") == "prod_001"
            else None,
            count=1,
        ),
        Brands=FakeCollection(find_one_fn=lambda _q: {"id": "brand_01", "name": "Logi"}),
        Categories=FakeCollection(
            rows=[{"id": "cat_01", "name": "Accessories"}],
            find_one_fn=lambda _q: {"id": "cat_01", "name": "Accessories"},
        ),
        Orders=FakeCollection(
            rows=[{"id": "ord_001", "userId": "user_1", "status": "shipped", "amount": 120}],
            find_one_fn=lambda q: {"status": "shipped"} if q.get("id") == "ord_001" else None,
            count=1,
        ),
        Reviews=FakeCollection(rows=[{"productId": "prod_001", "rating": 5}], count=1),
        Users=FakeCollection(rows=[{"id": "user_1", "name": "Ray"}], count=1),
        SupportTickets=FakeCollection(rows=[{"ticketId": "ticket_123", "subject": "Issue"}], count=1),
    )

    # Patch all API modules that import `db` directly.
    monkeypatch.setattr(products, "db", fake_db)
    monkeypatch.setattr(categories, "db", fake_db)
    monkeypatch.setattr(orders, "db", fake_db)
    monkeypatch.setattr(reviews, "db", fake_db)
    monkeypatch.setattr(support_tickets, "db", fake_db)
    monkeypatch.setattr(inventory, "db", fake_db)
    monkeypatch.setattr(analytics, "db", fake_db)
    monkeypatch.setattr(users, "db", fake_db)
    monkeypatch.setattr(search, "db", fake_db)

    # Patch chat dependencies.
    async def fake_get_master_user_session(_user_id):
        return None

    async def fake_get_session(session_id):
        return {"sessionId": session_id, "messages": []}

    async def fake_create_session(session_id, user_id):
        return {"sessionId": session_id, "userId": user_id, "messages": []}

    async def fake_link_session_to_user(_session_id, _user_id):
        return None

    async def fake_update_messages(_session_id, _messages):
        return None

    async def fake_run_agent(_message, history):
        history.append({"role": "assistant", "content": "Mock reply"})
        return "Mock reply"

    monkeypatch.setattr(chat.ChatRepository, "get_master_user_session", staticmethod(fake_get_master_user_session))
    monkeypatch.setattr(chat.ChatRepository, "get_session", staticmethod(fake_get_session))
    monkeypatch.setattr(chat.ChatRepository, "create_session", staticmethod(fake_create_session))
    monkeypatch.setattr(chat.ChatRepository, "link_session_to_user", staticmethod(fake_link_session_to_user))
    monkeypatch.setattr(chat.ChatRepository, "update_messages", staticmethod(fake_update_messages))
    monkeypatch.setattr(chat, "run_agent", fake_run_agent)

    return TestClient(app)


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200


def test_products_endpoints(client):
    assert client.get("/products/").status_code == 200
    assert client.get("/products/search", params={"q": "mouse"}).status_code == 200
    assert client.get("/products/prod_001").status_code == 200


def test_categories_endpoint(client):
    assert client.get("/categories/").status_code == 200


def test_orders_endpoints(client):
    assert client.get("/orders/").status_code == 200
    assert client.get("/orders/ord_001/status").status_code == 200
    assert client.get("/orders/user/user_1").status_code == 200


def test_reviews_endpoints(client):
    assert client.get("/reviews/").status_code == 200
    assert client.get("/reviews/product/prod_001").status_code == 200


def test_support_tickets_endpoints(client):
    payload = {
        "userId": "user_1",
        "orderId": "ord_001",
        "subject": "Late delivery",
        "message": "Package delayed",
    }
    assert client.post("/support-tickets/", json=payload).status_code == 200
    assert client.get("/support-tickets/").status_code == 200


def test_inventory_endpoint(client):
    assert client.get("/inventory/low-stock", params={"threshold": 10}).status_code == 200


def test_analytics_endpoints(client):
    assert client.get("/analytics/dashboard").status_code == 200
    assert client.get("/analytics/top-products").status_code == 200
    assert client.get("/analytics/sales").status_code == 200


def test_users_endpoint(client):
    assert client.get("/users/").status_code == 200


def test_search_endpoints(client):
    assert client.get("/search/", params={"q": "mouse"}).status_code == 200
    assert client.get("/search/advanced", params={"name": "Mouse"}).status_code == 200


def test_chat_endpoint(client):
    r = client.post("/chat/session_1", json={"message": "Do you have a mouse?", "user_id": "user_1"})
    assert r.status_code == 200
    assert r.json()["reply"] == "Mock reply"


### to test run:   pytest testing/test_all_api.py -v

