"""Фикстуры: все четыре сервиса и веб поднимаются в памяти, у каждого своя временная БД.
Вызовы между сервисами идут через Flask test client вместо сети."""
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parent.parent
for path in [ROOT, *(ROOT / "services" / name for name in ("tools", "customers", "rentals", "maintenance", "web"))]:
    sys.path.insert(0, str(path))

from common import client  # noqa: E402
from common.errors import ServiceUnavailable  # noqa: E402
import tools_app, customers_app, rentals_app, maintenance_app, web_app  # noqa: E402

URLS = {
    "tools": "http://tools.test",
    "customers": "http://customers.test",
    "rentals": "http://rentals.test",
    "maintenance": "http://maintenance.test",
}


class Cluster:
    """Набор сервисов с возможностью «выключить» любой из них."""

    def __init__(self, tmp_path):
        self.apps = {
            "tools": tools_app.app, "customers": customers_app.app,
            "rentals": rentals_app.app, "maintenance": maintenance_app.app,
        }
        self.down = set()
        for name, flask_app in self.apps.items():
            flask_app.config.update(TESTING=True, DATABASE=str(tmp_path / f"{name}.sqlite"))
            for key, url in URLS.items():
                if f"{key.upper()}_URL" in flask_app.config:
                    flask_app.config[f"{key.upper()}_URL"] = url
        web_app.app.config.update(TESTING=True, SECRET_KEY="test-secret",
                                  **{f"{k.upper()}_URL": v for k, v in URLS.items()})
        self.by_host = {urlsplit(url).netloc: name for name, url in URLS.items()}
        client.set_transport(self.transport)

    def transport(self, method, url, json_body, params):
        parts = urlsplit(url)
        name = self.by_host[parts.netloc]
        if name in self.down:
            raise ServiceUnavailable("down")
        with self.apps[name].test_client() as c:
            resp = c.open(parts.path, method=method, json=json_body, query_string=params)
        return resp.status_code, resp.get_json(silent=True)

    def api(self, name):
        return self.apps[name].test_client()


@pytest.fixture()
def cluster(tmp_path):
    yield Cluster(tmp_path)
    client.set_transport(None)


@pytest.fixture()
def web(cluster):
    with web_app.app.test_client() as c:
        yield c


# --- помощники для создания данных через API ---
@pytest.fixture()
def seed(cluster):
    class Seed:
        def category(self, name="Электроинструмент"):
            r = cluster.api("tools").post("/api/categories", json={"name": name, "description": "d"})
            assert r.status_code == 201, r.get_json()
            return r.get_json()

        def tool(self, name="Перфоратор", available=True, **extra):
            cat = self.category() if not cluster.api("tools").get("/api/categories").get_json() \
                else cluster.api("tools").get("/api/categories").get_json()[0]
            body = {"name": name, "brand": "B", "serial_number": "S", "category_id": cat["id"],
                    "daily_rate": "800", "condition": "Хорошее", "available": available, **extra}
            r = cluster.api("tools").post("/api/tools", json=body)
            assert r.status_code == 201, r.get_json()
            return r.get_json()

        def customer(self, name="Иван Иванов"):
            r = cluster.api("customers").post("/api/customers", json={"full_name": name, "phone": "+7 900"})
            assert r.status_code == 201, r.get_json()
            return r.get_json()

        def rental(self, tool_id, customer_id, start="2026-10-10", end="2026-10-12",
                   status="Забронирована", price="1600"):
            return cluster.api("rentals").post("/api/rentals", json={
                "tool_id": tool_id, "customer_id": customer_id, "start_date": start,
                "end_date": end, "status": status, "total_price": price})
    return Seed()
