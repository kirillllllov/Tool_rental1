def test_customer_crud(cluster, seed):
    c = cluster.api("customers")
    customer = seed.customer()
    assert c.get("/api/customers?q=Иван").get_json()[0]["id"] == customer["id"]
    r = c.put(f"/api/customers/{customer['id']}", json={"full_name": "Пётр", "phone": "+7 911"})
    assert r.get_json()["full_name"] == "Пётр"
    assert c.delete(f"/api/customers/{customer['id']}").status_code == 204
    assert c.get(f"/api/customers/{customer['id']}").status_code == 404


def test_customer_requires_name_and_phone(cluster):
    c = cluster.api("customers")
    assert "ФИО" in c.post("/api/customers", json={"phone": "1"}).get_json()["error"]
    assert "Телефон" in c.post("/api/customers", json={"full_name": "X"}).get_json()["error"]


def test_cannot_delete_customer_with_rentals(cluster, seed):
    tool, customer = seed.tool(), seed.customer()
    seed.rental(tool["id"], customer["id"])
    assert cluster.api("customers").delete(f"/api/customers/{customer['id']}").status_code == 409


def test_non_json_body_rejected(cluster):
    r = cluster.api("customers").post("/api/customers", data="x=1")
    assert r.status_code == 400
