"""Регистрация типового REST-ресурса (list / get / create / update / delete / schema)."""
import sqlite3

from flask import jsonify, request

from .errors import Conflict, NotFound, ValidationError
from .validation import clean


def _translate(exc):
    message = str(exc)
    if "UNIQUE" in message:
        return ValidationError("Запись с таким уникальным значением уже существует.")
    if "FOREIGN KEY" in message:
        return ValidationError("Выбранная связанная запись не существует.")
    if "CHECK constraint" in message:
        return ValidationError("Проверьте корректность дат и числовых значений.")
    return ValidationError("Не удалось сохранить запись. Проверьте введённые данные.")


def register_resource(app, *, db, path, table, alias, fields, select_sql,
                      search=(), filters=(), validate=None, check_delete=None):
    """
    db            — функция без аргументов, возвращающая контекстный менеджер с соединением;
    select_sql    — SELECT с алиасом таблицы `alias` (допускает JOIN-ы внутри сервиса);
    filters       — имена колонок, по которым работает фильтр ?колонка=значение;
    validate      — validate(values, existing) для бизнес-правил (existing=None при создании);
    check_delete  — check_delete(row), бросает Conflict, если удалять нельзя.
    """

    def fetch(conn, record_id):
        row = conn.execute(f"{select_sql} WHERE {alias}.id=?", (record_id,)).fetchone()
        if row is None:
            raise NotFound("Запись не найдена.")
        return dict(row)

    def body():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ValidationError("Ожидается JSON-объект.")
        return payload

    def list_records():
        where, params = [], []
        for column in filters:
            value = request.args.get(column)
            if value not in (None, ""):
                where.append(f"{alias}.{column}=?")
                params.append(value)
        q = request.args.get("q", "").strip()
        if q and search:
            clause = " OR ".join(f"CAST({alias}.{col} AS TEXT) LIKE ?" for col in search)
            where.append(f"({clause})")
            params.extend([f"%{q}%"] * len(search))
        sql = select_sql
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {alias}.id DESC"
        with db() as conn:
            return jsonify([dict(row) for row in conn.execute(sql, params).fetchall()])

    def get_record(record_id):
        with db() as conn:
            return jsonify(fetch(conn, record_id))

    def create_record():
        values = clean(fields, body())
        if validate:
            validate(values, None)
        names = list(values)
        try:
            with db() as conn:
                cur = conn.execute(
                    f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})",
                    [values[n] for n in names],
                )
                record = fetch(conn, cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise _translate(exc) from exc
        return jsonify(record), 201

    def update_record(record_id):
        values = clean(fields, body())
        with db() as conn:
            existing = fetch(conn, record_id)
        if validate:
            validate(values, existing)
        names = list(values)
        try:
            with db() as conn:
                conn.execute(
                    f"UPDATE {table} SET {', '.join(f'{n}=?' for n in names)} WHERE id=?",
                    [values[n] for n in names] + [record_id],
                )
                record = fetch(conn, record_id)
        except sqlite3.IntegrityError as exc:
            raise _translate(exc) from exc
        return jsonify(record)

    def delete_record(record_id):
        with db() as conn:
            existing = fetch(conn, record_id)
        if check_delete:
            check_delete(existing)
        try:
            with db() as conn:
                conn.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
        except sqlite3.IntegrityError as exc:
            raise Conflict("Нельзя удалить запись: она используется в связанных данных.") from exc
        return "", 204

    def schema():
        return jsonify(fields)

    app.add_url_rule(path, f"{table}_list", list_records, methods=["GET"])
    app.add_url_rule(path, f"{table}_create", create_record, methods=["POST"])
    app.add_url_rule(f"{path}/schema", f"{table}_schema", schema, methods=["GET"])
    app.add_url_rule(f"{path}/<int:record_id>", f"{table}_get", get_record, methods=["GET"])
    app.add_url_rule(f"{path}/<int:record_id>", f"{table}_update", update_record, methods=["PUT"])
    app.add_url_rule(f"{path}/<int:record_id>", f"{table}_delete", delete_record, methods=["DELETE"])
