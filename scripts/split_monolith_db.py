"""Перенос данных из старой монолитной базы (instance/rental.db) в базы микросервисов.

    python scripts/split_monolith_db.py instance/rental.db instance/

Создаёт в целевой папке tools.db, customers.db, rentals.db, maintenance.db с теми же id.
Для Docker положите файлы в тома сервисов (см. README, раздел «Миграция данных»).
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for name in ("tools", "customers", "rentals", "maintenance"):
    sys.path.insert(0, str(ROOT / "services" / name))

import customers_app, maintenance_app, rentals_app, tools_app  # noqa: E402
from common.db import session  # noqa: E402

PLAN = [  # (файл, схема сервиса, таблицы)
    ("tools.db", tools_app.SCHEMA, ["categories", "tools"]),
    ("customers.db", customers_app.SCHEMA, ["customers"]),
    ("rentals.db", rentals_app.SCHEMA, ["rentals"]),
    ("maintenance.db", maintenance_app.SCHEMA, ["maintenance"]),
]


def main(source, target_dir):
    source, target_dir = Path(source), Path(target_dir)
    if not source.exists():
        sys.exit(f"Не найден файл {source}")
    src = sqlite3.connect(source)
    src.row_factory = sqlite3.Row
    for filename, schema, tables in PLAN:
        target = target_dir / filename
        if target.exists():
            sys.exit(f"{target} уже существует — удалите его или выберите другую папку.")
        with session(target, schema) as dst:
            for table in tables:
                rows = src.execute(f"SELECT * FROM {table}").fetchall()
                if rows:
                    cols = rows[0].keys()
                    dst.executemany(
                        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                        [tuple(row) for row in rows])
                print(f"{filename}: {table} — {len(rows)} зап.")
    src.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
