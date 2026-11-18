def test_rental_crud(cluster, seed):
    tool, customer = seed.tool(), seed.customer()
    c = cluster.api("rentals")
    r = seed.rental(tool["id"], customer["id"])
    assert r.status_code == 201
    rid = r.get_json()["id"]
    body = {**r.get_json(), "status": "Активна"}
    assert c.put(f"/api/rentals/{rid}", json=body).get_json()["status"] == "Активна"
    assert c.get(f"/api/rentals?customer_id={customer['id']}").get_json()[0]["id"] == rid
    assert c.get("/api/rentals?status=Завершена").get_json() == []
    assert c.delete(f"/api/rentals/{rid}").status_code == 204


def test_end_date_before_start_rejected(cluster, seed):
    tool, customer = seed.tool(), seed.customer()
    r = seed.rental(tool["id"], customer["id"], start="2026-10-15", end="2026-10-10")
    assert r.status_code == 400
    assert "Дата окончания не может быть раньше даты начала" in r.get_json()["error"]


def test_unknown_tool_or_customer_rejected(cluster, seed):
    tool, customer = seed.tool(), seed.customer()
    assert seed.rental(999, customer["id"]).status_code == 400
    assert seed.rental(tool["id"], 999).status_code == 400


def test_unavailable_tool_cannot_be_rented(cluster, seed):
    tool, customer = seed.tool(available=False), seed.customer()
    r = seed.rental(tool["id"], customer["id"])
    assert r.status_code == 409 and "недоступен" in r.get_json()["error"]
    # завершённую (историческую) аренду записать можно
    assert seed.rental(tool["id"], customer["id"], status="Завершена").status_code == 201


def test_overlapping_rentals_rejected(cluster, seed):
    tool, customer = seed.tool(), seed.customer()
    assert seed.rental(tool["id"], customer["id"], "2026-10-10", "2026-10-12").status_code == 201
    r = seed.rental(tool["id"], customer["id"], "2026-10-12", "2026-10-14")
    assert r.status_code == 409 and "занят" in r.get_json()["error"]
    assert seed.rental(tool["id"], customer["id"], "2026-10-13", "2026-10-14").status_code == 201
    # другой инструмент на те же даты — можно
    other = seed.tool("Дрель")
    assert seed.rental(other["id"], customer["id"], "2026-10-10", "2026-10-12").status_code == 201


def test_cancelled_rental_does_not_block_and_edit_does_not_clash_with_itself(cluster, seed):
    tool, customer = seed.tool(), seed.customer()
    first = seed.rental(tool["id"], customer["id"], "2026-10-10", "2026-10-12").get_json()
    c = cluster.api("rentals")
    assert c.put(f"/api/rentals/{first['id']}", json={**first, "status": "Активна"}).status_code == 200
    c.put(f"/api/rentals/{first['id']}", json={**first, "status": "Отменена"})
    assert seed.rental(tool["id"], customer["id"], "2026-10-10", "2026-10-12").status_code == 201


def test_tools_service_down(cluster, seed):
    tool, customer = seed.tool(), seed.customer()
    cluster.down.add("tools")
    assert seed.rental(tool["id"], customer["id"]).status_code == 503
