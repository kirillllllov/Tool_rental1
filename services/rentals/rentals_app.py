"""Сервис «Аренды»: оформление и учёт аренды инструментов.

Хранит только идентификаторы инструмента и клиента (tool_id, customer_id).
Существование и доступность инструмента, существование клиента проверяет по HTTP
у сервисов «Инструменты» и «Клиенты».
"""
import os
from pathlib import Path

from flask import Flask

from common import client, errors
from common.db import session
from common.errors import Conflict, ServiceUnavailable, ValidationError
from common.resource import register_resource

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config.update(
    DATABASE=os.environ.get("DATABASE", str(BASE_DIR / "instance" / "rentals.db")),
    TOOLS_URL=os.environ.get("TOOLS_URL", "http://127.0.0.1:5001"),
    CUSTOMERS_URL=os.environ.get("CUSTOMERS_URL", "http://127.0.0.1:5002"),
)
errors.install(app, "rentals")

# tool_id и customer_id — ссылки на чужие сервисы, поэтому FOREIGN KEY здесь нет.
SCHEMA = """
CREATE TABLE IF NOT EXISTS rentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Забронирована',
    total_price REAL NOT NULL CHECK(total_price >= 0),
    notes TEXT NOT NULL DEFAULT '',
    CHECK(end_date >= start_date)
);
"""

STATUSES = ["Забронирована", "Активна", "Завершена", "Отменена"]
BUSY_STATUSES = ("Забронирована", "Активна")  # статусы, при которых инструмент занят

RENTAL_FIELDS = [
    {"name": "tool_id", "label": "Инструмент", "type": "select", "ref": "tools", "required": True},
    {"name": "customer_id", "label": "Клиент", "type": "select", "ref": "customers", "required": True},
    {"name": "start_date", "label": "Дата начала", "type": "date", "required": True},
    {"name": "end_date", "label": "Дата окончания", "type": "date", "required": True},
    {"name": "status", "label": "Статус", "type": "choice", "options": STATUSES, "required": True},
    {"name": "total_price", "label": "Итоговая стоимость (₽)", "type": "number", "step": "0.01", "required": True},
    {"name": "notes", "label": "Примечание", "type": "textarea"},
]

NOT_FOUND_REF = "Выбранная связанная запись не существует."


def db():
    return session(app.config["DATABASE"], SCHEMA)


def remote_get(url_key, path):
    status, data = client.request("GET", app.config[url_key] + path)
    if status == 404:
        return None
    if status != 200:
        raise ServiceUnavailable("Сервис временно недоступен. Попробуйте позже.")
    return data


def validate_rental(values, existing):
    if values["end_date"] < values["start_date"]:
        raise ValidationError("Дата окончания не может быть раньше даты начала.")

    tool = remote_get("TOOLS_URL", f"/api/tools/{values['tool_id']}")
    if tool is None:
        raise ValidationError(NOT_FOUND_REF)
    if remote_get("CUSTOMERS_URL", f"/api/customers/{values['customer_id']}") is None:
        raise ValidationError(NOT_FOUND_REF)

    if values["status"] not in BUSY_STATUSES:
        return

    # Правило 1: нельзя бронировать/выдавать недоступный инструмент
    # (проверяем при создании и когда аренда становится «занятой» или переносится на другой инструмент).
    newly_busy = (existing is None or existing["status"] not in BUSY_STATUSES
                  or existing["tool_id"] != values["tool_id"])
    if newly_busy and not tool["available"]:
        raise Conflict("Инструмент недоступен для аренды.")

    # Правило 2: один инструмент нельзя сдать двум клиентам на пересекающиеся даты.
    marks = ",".join("?" for _ in BUSY_STATUSES)
    with db() as conn:
        clash = conn.execute(
            f"""SELECT id FROM rentals
                WHERE tool_id=? AND status IN ({marks}) AND id != ?
                  AND start_date <= ? AND end_date >= ?
                ORDER BY id LIMIT 1""",
            [values["tool_id"], *BUSY_STATUSES, existing["id"] if existing else 0,
             values["end_date"], values["start_date"]],
        ).fetchone()
    if clash:
        raise Conflict(f"Инструмент уже занят в выбранный период (аренда №{clash['id']}).")


register_resource(
    app, db=db, path="/api/rentals", table="rentals", alias="r", fields=RENTAL_FIELDS,
    select_sql="SELECT r.* FROM rentals r",
    search=["status", "start_date", "end_date"],
    filters=["tool_id", "customer_id", "status"],
    validate=validate_rental,
)

if __name__ == "__main__":
    app.run(port=5003)
