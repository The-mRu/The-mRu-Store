import sys
from pathlib import Path

# Ensure project root is importable when running this file directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from main_db_server import app


def _get_client():
    # Lazy import prevents deprecation warnings when this file is run directly.
    from fastapi.testclient import TestClient

    return TestClient(app)

def test_root():
    client = _get_client()
    r = client.get("/")
    assert r.status_code == 200
    assert "message" in r.json()   

def test_inventory_low_stock():
    client = _get_client()
    r = client.get("/inventory/low-stock?threshold=10")
    assert r.status_code in (200, 404)


if __name__ == "__main__":
    print("Run tests with: python -m pytest testing/api_testing1.py -q")