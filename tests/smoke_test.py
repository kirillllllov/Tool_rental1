"""Дымовые тесты запущенной системы (через nginx-шлюз). Запуск:
    BASE_URL=http://localhost python -m pytest tests/smoke_test.py
В обычный прогон `pytest` не входят (нужна поднятая система)."""
import os
import uuid

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost")


@pytest.fixture()
def session():
    with requests.Session() as s:
        yield s


def test_web_is_up():
    r = requests.get(f"{BASE_URL}/", timeout=5)
    assert r.status_code == 200
    assert "Система аренды" in r.text


@pytest.mark.parametrize("path", ["/api/tools", "/api/categories", "/api/customers",
                                  "/api/rentals", "/api/maintenance"])
def test_api_routed_to_each_service(path):
    r = requests.get(f"{BASE_URL}{path}", timeout=5)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_category_created_via_ui(session):
    name = f"SmokeCategory-{uuid.uuid4().hex[:8]}"
    r = session.post(f"{BASE_URL}/categories/new", data={"name": name, "description": "Smoke test"},
                     allow_redirects=True, timeout=5)
    assert r.status_code == 200
    assert name in r.text


def test_negative_price_rejected(session):
    r = session.post(f"{BASE_URL}/tools/new",
                     data={"name": "SmokeTool", "category_id": "1", "daily_rate": "-5",
                           "condition": "Хорошее", "available": "on"},
                     allow_redirects=True, timeout=5)
    assert r.status_code == 200
    assert "не может быть отрицательным" in r.text
