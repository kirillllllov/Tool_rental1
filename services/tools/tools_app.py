"""Сервис «Инструменты»: каталог инструментов и их категории.

Владеет данными: categories, tools. Собственная БД (instance/tools.db).
Перед удалением инструмента спрашивает сервисы «Аренды» и «Обслуживание», не ссылаются ли они на него.
"""
import os
from pathlib import Path

from flask import Flask

from common import client, errors
from common.db import session
from common.errors import Conflict, ServiceUnavailable
from common.resource import register_resource

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config.update(
    DATABASE=os.environ.get("DATABASE", str(BASE_DIR / "instance" / "tools.db")),
    RENTALS_URL=os.environ.get("RENTALS_URL", "http://127.0.0.1:5003"),
    MAINTENANCE_URL=os.environ.get("MAINTENANCE_URL", "http://127.0.0.1:5004"),
)
errors.install(app, "tools")

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    serial_number TEXT NOT NULL DEFAULT '',
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    daily_rate REAL NOT NULL CHECK(daily_rate >= 0),
    condition TEXT NOT NULL DEFAULT 'Хорошее',
    available INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL DEFAULT ''
);
"""

CATEGORY_FIELDS = [
    {"name": "name", "label": "Название", "type": "text", "required": True},
    {"name": "description", "label": "Описание", "type": "textarea"},
]

TOOL_FIELDS = [
    {"name": "name", "label": "Название", "type": "text", "required": True},
    {"name": "brand", "label": "Производитель", "type": "text"},
    {"name": "serial_number", "label": "Серийный номер", "type": "text"},
    {"name": "category_id", "label": "Категория", "type": "select", "ref": "categories", "required": True},
    {"name": "daily_rate", "label": "Цена за сутки (₽)", "type": "number", "step": "0.01", "required": True},
    {"name": "condition", "label": "Состояние", "type": "choice", "required": True,
     "options": ["Отличное", "Хорошее", "Удовлетворительное", "На ремонте"]},
    {"name": "available", "label": "Доступен для аренды", "type": "bool", "default": True},
    {"name": "description", "label": "Описание", "type": "textarea"},
]

IN_USE = "Нельзя удалить запись: она используется в связанных данных."


def db():
    return session(app.config["DATABASE"], SCHEMA)


def check_category_delete(row):
    with db() as conn:
        used = conn.execute("SELECT COUNT(*) FROM tools WHERE category_id=?", (row["id"],)).fetchone()[0]
    if used:
        raise Conflict("Нельзя удалить категорию: в ней есть инструменты.")


def check_tool_delete(row):
    """Бизнес-правило: нельзя удалить инструмент, у которого есть аренды или записи обслуживания."""
    for url_key, path in (("RENTALS_URL", "/api/rentals"), ("MAINTENANCE_URL", "/api/maintenance")):
        status, data = client.request("GET", app.config[url_key] + path, params={"tool_id": row["id"]})
        if status != 200:
            raise ServiceUnavailable("Не удалось проверить связанные данные: сервис недоступен.")
        if data:
            raise Conflict(IN_USE)


register_resource(
    app, db=db, path="/api/categories", table="categories", alias="c", fields=CATEGORY_FIELDS,
    select_sql="SELECT c.* FROM categories c", search=["name", "description"],
    check_delete=check_category_delete,
)

register_resource(
    app, db=db, path="/api/tools", table="tools", alias="t", fields=TOOL_FIELDS,
    select_sql="SELECT t.*, c.name AS category_name FROM tools t JOIN categories c ON c.id=t.category_id",
    search=["name", "brand", "serial_number"], filters=["category_id", "available"],
    check_delete=check_tool_delete,
)

if __name__ == "__main__":
    app.run(port=5001)
