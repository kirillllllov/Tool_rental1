"""Сквозные проверки интерфейса: web -> API четырёх сервисов."""


def post_category(web, name="Электроинструмент"):
    return web.post("/categories/new", data={"name": name, "description": "d"}, follow_redirects=True)


def tool_form(**extra):
    return {"name": "Перфоратор", "brand": "B", "serial_number": "PB-1", "category_id": "1",
            "daily_rate": "800", "condition": "Хорошее", "available": "on", "description": "", **extra}


def test_dashboard_loads(web):
    r = web.get("/")
    assert r.status_code == 200
    assert "Система аренды строительных инструментов".encode() in r.data


def test_category_crud_via_ui(web):
    assert "Электроинструмент".encode() in post_category(web).data
    r = web.post("/categories/1/edit", data={"name": "Ручной инструмент", "description": ""}, follow_redirects=True)
    assert "Ручной инструмент".encode() in r.data
    assert "Записи не найдены".encode() in web.post("/categories/1/delete", follow_redirects=True).data


def test_tool_crud_via_ui(web):
    post_category(web)
    r = web.post("/tools/new", data=tool_form(), follow_redirects=True)
    assert "Перфоратор".encode() in r.data and "Электроинструмент".encode() in r.data
    r = web.post("/tools/1/edit", data=tool_form(name="Перфоратор PRO", daily_rate="950"), follow_redirects=True)
    assert "Перфоратор PRO".encode() in r.data
    assert "Записи не найдены".encode() in web.post("/tools/1/delete", follow_redirects=True).data


def test_unchecked_checkbox_makes_tool_unavailable(web):
    post_category(web)
    data = tool_form()
    data.pop("available")
    web.post("/tools/new", data=data, follow_redirects=True)
    assert "Недоступен".encode() in web.get("/tools").data


def test_tool_search_works(web):
    post_category(web)
    web.post("/tools/new", data=tool_form(), follow_redirects=True)
    assert "Перфоратор".encode() in web.get("/tools?q=Перф").data
    assert "Записи не найдены".encode() in web.get("/tools?q=zzz").data


def test_customer_crud_via_ui(web):
    web.post("/customers/new", data={"full_name": "Иван Иванов", "phone": "+7 900", "email": "", "document_number": ""})
    assert "Иван Иванов".encode() in web.get("/customers").data
    r = web.post("/customers/1/edit", data={"full_name": "Пётр Петров", "phone": "+7 911", "email": "", "document_number": ""},
                 follow_redirects=True)
    assert "Пётр Петров".encode() in r.data
    assert "Записи не найдены".encode() in web.post("/customers/1/delete", follow_redirects=True).data


def rental_form(**extra):
    return {"tool_id": "1", "customer_id": "1", "start_date": "2026-10-10", "end_date": "2026-10-12",
            "status": "Забронирована", "total_price": "1600", "notes": "", **extra}


def prepare(web):
    post_category(web)
    web.post("/tools/new", data=tool_form())
    web.post("/customers/new", data={"full_name": "Иван Иванов", "phone": "+7 900"})


def test_rental_crud_via_ui(web):
    prepare(web)
    web.post("/rentals/new", data=rental_form())
    page = web.get("/rentals").data
    assert "Перфоратор".encode() in page and "Иван Иванов".encode() in page
    r = web.post("/rentals/1/edit", data=rental_form(status="Активна"), follow_redirects=True)
    assert "Активна".encode() in r.data
    assert "Записи не найдены".encode() in web.post("/rentals/1/delete", follow_redirects=True).data


def test_rental_rules_shown_to_user(web):
    prepare(web)
    r = web.post("/rentals/new", data=rental_form(start_date="2026-10-15", end_date="2026-10-10"), follow_redirects=True)
    assert "Дата окончания не может быть раньше даты начала".encode() in r.data
    web.post("/rentals/new", data=rental_form())
    r = web.post("/rentals/new", data=rental_form(start_date="2026-10-11"), follow_redirects=True)
    assert "уже занят".encode() in r.data


def test_cannot_delete_used_tool_and_customer(web):
    prepare(web)
    web.post("/rentals/new", data=rental_form())
    assert "используется".encode() in web.post("/tools/1/delete", follow_redirects=True).data
    assert "используется".encode() in web.post("/customers/1/delete", follow_redirects=True).data


def test_maintenance_crud_via_ui(web):
    prepare(web)
    data = {"tool_id": "1", "service_date": "2026-10-01", "service_type": "Проверка", "cost": "500", "notes": ""}
    web.post("/maintenance/new", data=data)
    assert "Проверка".encode() in web.get("/maintenance").data
    r = web.post("/maintenance/1/edit", data={**data, "service_type": "Замена щёток"}, follow_redirects=True)
    assert "Замена щёток".encode() in r.data
    assert "Записи не найдены".encode() in web.post("/maintenance/1/delete", follow_redirects=True).data


def test_negative_price_is_rejected(web):
    post_category(web)
    r = web.post("/tools/new", data=tool_form(daily_rate="-5"), follow_redirects=True)
    assert "не может быть отрицательным".encode() in r.data


def test_unknown_entity_and_record_404(web):
    assert web.get("/nothing").status_code == 404
    assert web.get("/tools/99/edit").status_code == 404


def test_page_shows_503_when_service_down(cluster, web):
    cluster.down.add("rentals")
    r = web.get("/rentals")
    assert r.status_code == 503 and "недоступен".encode() in r.data
    assert web.get("/status").get_json()["rentals"] == "down"
    assert web.get("/status").get_json()["tools"] == "ok"
