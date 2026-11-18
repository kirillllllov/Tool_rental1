from datetime import date

from .errors import ValidationError

TRUE_VALUES = (True, 1, "1", "on", "true", "True")


def clean(fields, payload):
    """Проверяет JSON-тело по описанию полей и возвращает значения для записи в БД.

    Типы полей: text, email, textarea, date, number, select (id связанной записи),
    choice (одно значение из options), bool.
    """
    values = {}
    for field in fields:
        name, kind, label = field["name"], field["type"], field["label"]

        if kind == "bool":
            if name in payload:
                values[name] = 1 if payload[name] in TRUE_VALUES else 0
            else:
                values[name] = 1 if field.get("default") else 0
            continue

        raw = payload.get(name)
        if isinstance(raw, str):
            raw = raw.strip()
        empty = raw is None or raw == ""

        if field.get("required") and empty:
            raise ValidationError(f"Поле «{label}» обязательно для заполнения.")
        if empty:
            values[name] = 0 if kind == "number" else ""
            continue

        if kind == "number":
            try:
                value = float(raw)
            except (TypeError, ValueError):
                raise ValidationError(f"Поле «{label}» должно быть числом.")
            if value < 0:
                raise ValidationError(f"Поле «{label}» не может быть отрицательным.")
            values[name] = value
        elif kind == "select":
            try:
                values[name] = int(raw)
            except (TypeError, ValueError):
                raise ValidationError(f"Выберите корректное значение поля «{label}».")
        elif kind == "choice":
            if raw not in field["options"]:
                raise ValidationError(f"Недопустимое значение поля «{label}».")
            values[name] = raw
        elif kind == "date":
            try:
                date.fromisoformat(str(raw))
            except ValueError:
                raise ValidationError(f"Поле «{label}» должно быть датой в формате ГГГГ-ММ-ДД.")
            values[name] = str(raw)
        else:
            values[name] = str(raw)
    return values
