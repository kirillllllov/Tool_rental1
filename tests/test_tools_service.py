def test_health_and_schema(cluster):
    c = cluster.api("tools")
    assert c.get("/health").get_json() == {"service": "tools", "status": "ok"}
    names = [f["name"] for f in c.get("/api/tools/schema").get_json()]
    assert "daily_rate" in names


def test_category_crud(cluster, seed):
    c = cluster.api("tools")
    cat = seed.category()
    assert c.get(f"/api/categories/{cat['id']}").get_json()["name"] == "Электроинструмент"
    r = c.put(f"/api/categories/{cat['id']}", json={"name": "Ручной", "description": "x"})
    assert r.get_json()["name"] == "Ручной"
    assert c.delete(f"/api/categories/{cat['id']}").status_code == 204
    assert c.get("/api/categories").get_json() == []


def test_category_name_must_be_unique(cluster, seed):
    seed.category()
    r = cluster.api("tools").post("/api/categories", json={"name": "Электроинструмент"})
    assert r.status_code == 400 and "уникальным" in r.get_json()["error"]


def test_tool_crud_and_search(cluster, seed):
    c = cluster.api("tools")
    tool = seed.tool()
    assert tool["category_name"] == "Электроинструмент"
    assert c.get("/api/tools?q=Перфо").get_json()[0]["id"] == tool["id"]
    assert c.get("/api/tools?q=нет-такого").get_json() == []
    body = {**tool, "name": "Перфоратор PRO", "daily_rate": 950}
    assert c.put(f"/api/tools/{tool['id']}", json=body).get_json()["name"] == "Перфоратор PRO"
    assert c.delete(f"/api/tools/{tool['id']}").status_code == 204


def test_tool_validation(cluster, seed):
    cat = seed.category()
    c = cluster.api("tools")
    base = {"name": "Дрель", "category_id": cat["id"], "daily_rate": "100", "condition": "Хорошее"}
    assert "не может быть отрицательным" in c.post("/api/tools", json={**base, "daily_rate": "-5"}).get_json()["error"]
    assert "обязательно" in c.post("/api/tools", json={**base, "category_id": ""}).get_json()["error"]
    assert "Недопустимое" in c.post("/api/tools", json={**base, "condition": "Сломан"}).get_json()["error"]
    assert "не существует" in c.post("/api/tools", json={**base, "category_id": 99}).get_json()["error"]


def test_available_filter_and_default(cluster, seed):
    seed.tool("A", available=True)
    seed.tool("B", available=False)
    c = cluster.api("tools")
    assert [t["name"] for t in c.get("/api/tools?available=1").get_json()] == ["A"]
    cat = c.get("/api/categories").get_json()[0]
    r = c.post("/api/tools", json={"name": "C", "category_id": cat["id"], "daily_rate": 1, "condition": "Хорошее"})
    assert r.get_json()["available"] == 1  # по умолчанию доступен


def test_cannot_delete_category_with_tools(cluster, seed):
    tool = seed.tool()
    r = cluster.api("tools").delete(f"/api/categories/{tool['category_id']}")
    assert r.status_code == 409


def test_cannot_delete_tool_used_in_rental_or_maintenance(cluster, seed):
    tool, customer = seed.tool(), seed.customer()
    assert seed.rental(tool["id"], customer["id"]).status_code == 201
    assert cluster.api("tools").delete(f"/api/tools/{tool['id']}").status_code == 409

    other = seed.tool("Дрель")
    cluster.api("maintenance").post("/api/maintenance", json={
        "tool_id": other["id"], "service_date": "2026-10-01", "service_type": "Проверка", "cost": 1})
    assert cluster.api("tools").delete(f"/api/tools/{other['id']}").status_code == 409


def test_delete_tool_when_rentals_service_down(cluster, seed):
    tool = seed.tool()
    cluster.down.add("rentals")
    assert cluster.api("tools").delete(f"/api/tools/{tool['id']}").status_code == 503
    assert cluster.api("tools").get(f"/api/tools/{tool['id']}").status_code == 200
