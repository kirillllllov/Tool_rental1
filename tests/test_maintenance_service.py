def test_maintenance_crud(cluster, seed):
    tool = seed.tool()
    c = cluster.api("maintenance")
    data = {"tool_id": tool["id"], "service_date": "2026-10-01", "service_type": "Проверка",
            "cost": "500", "notes": "Плановое"}
    r = c.post("/api/maintenance", json=data)
    assert r.status_code == 201
    mid = r.get_json()["id"]
    assert c.put(f"/api/maintenance/{mid}", json={**data, "service_type": "Замена щёток"}).get_json()["service_type"] == "Замена щёток"
    assert c.get(f"/api/maintenance?tool_id={tool['id']}").get_json()[0]["id"] == mid
    assert c.delete(f"/api/maintenance/{mid}").status_code == 204


def test_maintenance_requires_existing_tool(cluster):
    r = cluster.api("maintenance").post("/api/maintenance", json={
        "tool_id": 5, "service_date": "2026-10-01", "service_type": "Проверка", "cost": 1})
    assert r.status_code == 400


def test_maintenance_validation(cluster, seed):
    tool = seed.tool()
    c = cluster.api("maintenance")
    base = {"tool_id": tool["id"], "service_date": "2026-10-01", "service_type": "Проверка", "cost": 1}
    assert "не может быть отрицательным" in c.post("/api/maintenance", json={**base, "cost": -1}).get_json()["error"]
    assert "датой" in c.post("/api/maintenance", json={**base, "service_date": "вчера"}).get_json()["error"]


def test_maintenance_when_tools_down(cluster, seed):
    tool = seed.tool()
    cluster.down.add("tools")
    r = cluster.api("maintenance").post("/api/maintenance", json={
        "tool_id": tool["id"], "service_date": "2026-10-01", "service_type": "Проверка", "cost": 1})
    assert r.status_code == 503
