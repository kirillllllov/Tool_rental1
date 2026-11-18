"""Сервис «Клиенты»: учёт арендаторов. Собственная БД (instance/customers.db)."""
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
    DATABASE=os.environ.get("DATABASE", str(BASE_DIR / "instance" / "customers.db")),
    RENTALS_URL=os.environ.get("RENTALS_URL", "http://127.0.0.1:5003"),
)
errors.install(app, "customers")

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    document_number TEXT NOT NULL DEFAULT ''
);
"""

CUSTOMER_FIELDS = [
    {"name": "full_name", "label": "ФИО", "type": "text", "required": True},
    {"name": "phone", "label": "Телефон", "type": "text", "required": True},
    {"name": "email", "label": "Электронная почта", "type": "email"},
    {"name": "document_number", "label": "Номер документа", "type": "text"},
]


def db():
    return session(app.config["DATABASE"], SCHEMA)


def check_customer_delete(row):
    """Бизнес-правило: нельзя удалить клиента, у которого есть аренды."""
    status, data = client.request("GET", app.config["RENTALS_URL"] + "/api/rentals",
                                  params={"customer_id": row["id"]})
    if status != 200:
        raise ServiceUnavailable("Не удалось проверить аренды клиента: сервис аренд недоступен.")
    if data:
        raise Conflict("Нельзя удалить запись: она используется в связанных данных.")


register_resource(
    app, db=db, path="/api/customers", table="customers", alias="c", fields=CUSTOMER_FIELDS,
    select_sql="SELECT c.* FROM customers c",
    search=["full_name", "phone", "email", "document_number"],
    check_delete=check_customer_delete,
)

if __name__ == "__main__":
    app.run(port=5002)
