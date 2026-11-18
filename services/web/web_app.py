"""Веб-интерфейс (фронтенд-сервис). Собственных данных не хранит:
все операции выполняет через REST API микросервисов — Инструменты, Клиенты, Аренды, Обслуживание.
"""
import os

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for

from common import client
from common.errors import ServiceUnavailable

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
    TOOLS_URL=os.environ.get("TOOLS_URL", "http://127.0.0.1:5001"),
    CUSTOMERS_URL=os.environ.get("CUSTOMERS_URL", "http://127.0.0.1:5002"),
    RENTALS_URL=os.environ.get("RENTALS_URL", "http://127.0.0.1:5003"),
    MAINTENANCE_URL=os.environ.get("MAINTENANCE_URL", "http://127.0.0.1:5004"),
)

# Какой сервис владеет какой сущностью и что показывать в таблице.
ENTITIES = {
    "tools": {
        "title": "Инструменты", "singular": "инструмент",
        "service": "TOOLS_URL", "path": "/api/tools",
        "columns": [("name", "Название"), ("brand", "Производитель"), ("category_name", "Категория"),
                    ("daily_rate", "Цена/сутки"), ("condition", "Состояние"), ("available_label", "Доступность")],
    },
    "categories": {
        "title": "Категории", "singular": "категорию",
        "service": "TOOLS_URL", "path": "/api/categories",
        "columns": [("name", "Название"), ("description", "Описание")],
    },
    "customers": {
        "title": "Клиенты", "singular": "клиента",
        "service": "CUSTOMERS_URL", "path": "/api/customers",
        "columns": [("full_name", "ФИО"), ("phone", "Телефон"), ("email", "Email"), ("document_number", "Документ")],
    },
    "rentals": {
        "title": "Аренды", "singular": "аренду",
        "service": "RENTALS_URL", "path": "/api/rentals",
        "columns": [("tool_name", "Инструмент"), ("customer_name", "Клиент"), ("start_date", "Начало"),
                    ("end_date", "Окончание"), ("status", "Статус"), ("total_price", "Стоимость")],
    },
    "maintenance": {
        "title": "Обслуживание", "singular": "запись обслуживания",
        "service": "MAINTENANCE_URL", "path": "/api/maintenance",
        "columns": [("tool_name", "Инструмент"), ("service_date", "Дата"), ("service_type", "Тип работ"),
                    ("cost", "Стоимость"), ("notes", "Примечание")],
    },
}

# Справочники для выпадающих списков: ссылка (ref) -> (сервис, путь, поле с подписью).
REFERENCES = {
    "categories": ("TOOLS_URL", "/api/categories", "name"),
    "tools": ("TOOLS_URL", "/api/tools", "name"),
    "customers": ("CUSTOMERS_URL", "/api/customers", "full_name"),
}


def call(service, method, path, json_body=None, params=None):
    return client.request(method, app.config[service] + path, json_body=json_body, params=params)


def entity_or_404(entity):
    if entity not in ENTITIES:
        abort(404)
    return ENTITIES[entity]


def load(service, path, params=None):
    status, data = call(service, "GET", path, params=params)
    if status != 200:
        raise ServiceUnavailable("Сервис вернул ошибку. Попробуйте позже.")
    return data


def reference_rows(ref):
    service, path, label = REFERENCES[ref]
    rows = [{"id": row["id"], "label": row[label]} for row in load(service, path)]
    return sorted(rows, key=lambda row: str(row["label"]).lower())


def enrich(entity, rows):
    """Подставляет названия из соседних сервисов (в чужих БД мы ничего не джойним)."""
    if entity == "tools":
        for row in rows:
            row["available_label"] = "Доступен" if row["available"] else "Недоступен"
    elif entity == "rentals" and rows:
        tools = {r["id"]: r["label"] for r in reference_rows("tools")}
        customers = {r["id"]: r["label"] for r in reference_rows("customers")}
        for row in rows:
            row["tool_name"] = tools.get(row["tool_id"], f"№{row['tool_id']} (удалён)")
            row["customer_name"] = customers.get(row["customer_id"], f"№{row['customer_id']} (удалён)")
    elif entity == "maintenance" and rows:
        tools = {r["id"]: r["label"] for r in reference_rows("tools")}
        for row in rows:
            row["tool_name"] = tools.get(row["tool_id"], f"№{row['tool_id']} (удалён)")
    return rows


def form_fields(entity):
    config = ENTITIES[entity]
    fields = load(config["service"], config["path"] + "/schema")
    for field in fields:
        if field["type"] == "select":
            field["options_data"] = reference_rows(field["ref"])
    return fields


def form_payload(form, fields):
    """Форма -> JSON. Снятый чекбокс браузер не отправляет, поэтому bool-поля задаём явно."""
    payload = {key: value for key, value in form.items()}
    for field in fields:
        if field["type"] == "bool":
            payload[field["name"]] = field["name"] in form
    return payload


def error_text(data):
    return (data or {}).get("error", "Не удалось выполнить операцию.")


@app.get("/health")
def health():
    return jsonify({"service": "web", "status": "ok"})


@app.get("/status")
def status():
    result = {}
    for name, key in (("tools", "TOOLS_URL"), ("customers", "CUSTOMERS_URL"),
                      ("rentals", "RENTALS_URL"), ("maintenance", "MAINTENANCE_URL")):
        try:
            code, _ = call(key, "GET", "/health")
            result[name] = "ok" if code == 200 else "error"
        except ServiceUnavailable:
            result[name] = "down"
    return jsonify(result)


@app.route("/")
def dashboard():
    stats = {
        "tools": len(load("TOOLS_URL", "/api/tools")),
        "available": len(load("TOOLS_URL", "/api/tools", {"available": 1})),
        "customers": len(load("CUSTOMERS_URL", "/api/customers")),
        "active_rentals": len(load("RENTALS_URL", "/api/rentals", {"status": "Активна"})),
    }
    recent = enrich("rentals", load("RENTALS_URL", "/api/rentals")[:5])
    return render_template("dashboard.html", stats=stats, recent=recent)


@app.route("/<entity>")
def list_records(entity):
    config = entity_or_404(entity)
    search = request.args.get("q", "")
    rows = enrich(entity, load(config["service"], config["path"], {"q": search.strip() or None}))
    return render_template("list.html", entity=entity, config=config, rows=rows,
                           search=search, columns=config["columns"])


@app.route("/<entity>/new", methods=["GET", "POST"])
def create_record(entity):
    config = entity_or_404(entity)
    fields = form_fields(entity)
    if request.method == "POST":
        code, data = call(config["service"], "POST", config["path"],
                          json_body=form_payload(request.form, fields))
        if code == 201:
            flash("Запись успешно создана.", "success")
            return redirect(url_for("list_records", entity=entity))
        flash(error_text(data), "error")
    return render_template("form.html", entity=entity, config=config, fields=fields,
                           record=None, heading=f"Добавить: {config['singular']}")


@app.route("/<entity>/<int:record_id>/edit", methods=["GET", "POST"])
def edit_record(entity, record_id):
    config = entity_or_404(entity)
    code, record = call(config["service"], "GET", f"{config['path']}/{record_id}")
    if code == 404:
        abort(404)
    if code != 200:
        raise ServiceUnavailable("Сервис вернул ошибку. Попробуйте позже.")
    fields = form_fields(entity)
    if request.method == "POST":
        code, data = call(config["service"], "PUT", f"{config['path']}/{record_id}",
                          json_body=form_payload(request.form, fields))
        if code == 200:
            flash("Изменения сохранены.", "success")
            return redirect(url_for("list_records", entity=entity))
        if code == 404:
            abort(404)
        flash(error_text(data), "error")
    return render_template("form.html", entity=entity, config=config, fields=fields,
                           record=record, heading=f"Редактировать: {config['singular']}")


@app.route("/<entity>/<int:record_id>/delete", methods=["POST"])
def delete_record(entity, record_id):
    config = entity_or_404(entity)
    code, data = call(config["service"], "DELETE", f"{config['path']}/{record_id}")
    if code == 404:
        abort(404)
    if code in (200, 204):
        flash("Запись удалена.", "success")
    else:
        flash(error_text(data), "error")
    return redirect(url_for("list_records", entity=entity))


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


@app.errorhandler(ServiceUnavailable)
def service_unavailable(exc):
    return render_template("503.html", message=exc.message), 503


if __name__ == "__main__":
    app.run(port=5000, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
