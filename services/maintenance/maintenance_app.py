"""Сервис «Обслуживание»: учёт технического обслуживания и ремонта инструментов.

Хранит tool_id; существование инструмента проверяет у сервиса «Инструменты».
"""
import os
from pathlib import Path

from flask import Flask

from common import client, errors
from common.db import session
from common.errors import ServiceUnavailable, ValidationError
from common.resource import register_resource

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config.update(
    DATABASE=os.environ.get("DATABASE", str(BASE_DIR / "instance" / "maintenance.db")),
    TOOLS_URL=os.environ.get("TOOLS_URL", "http://127.0.0.1:5001"),
)
errors.install(app, "maintenance")

SCHEMA = """
CREATE TABLE IF NOT EXISTS maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id INTEGER NOT NULL,
    service_date TEXT NOT NULL,
    service_type TEXT NOT NULL,
    cost REAL NOT NULL CHECK(cost >= 0),
    notes TEXT NOT NULL DEFAULT ''
);
"""

MAINTENANCE_FIELDS = [
    {"name": "tool_id", "label": "Инструмент", "type": "select", "ref": "tools", "required": True},
    {"name": "service_date", "label": "Дата обслуживания", "type": "date", "required": True},
    {"name": "service_type", "label": "Тип работ", "type": "text", "required": True},
    {"name": "cost", "label": "Стоимость (₽)", "type": "number", "step": "0.01", "required": True},
    {"name": "notes", "label": "Примечание", "type": "textarea"},
]


def db():
    return session(app.config["DATABASE"], SCHEMA)


def validate_maintenance(values, existing):
    status, _ = client.request("GET", f"{app.config['TOOLS_URL']}/api/tools/{values['tool_id']}")
    if status == 404:
        raise ValidationError("Выбранная связанная запись не существует.")
    if status != 200:
        raise ServiceUnavailable("Сервис инструментов временно недоступен. Попробуйте позже.")


register_resource(
    app, db=db, path="/api/maintenance", table="maintenance", alias="m", fields=MAINTENANCE_FIELDS,
    select_sql="SELECT m.* FROM maintenance m",
    search=["service_date", "service_type", "notes"], filters=["tool_id"],
    validate=validate_maintenance,
)

if __name__ == "__main__":
    app.run(port=5004)
