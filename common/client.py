"""Минимальный HTTP-клиент для вызовов между микросервисами (только стандартная библиотека)."""
import json
import urllib.error
import urllib.parse
import urllib.request

from .errors import ServiceUnavailable

_transport = None


def set_transport(func):
    """Подмена транспорта (используется в тестах, чтобы не поднимать реальные серверы)."""
    global _transport
    _transport = func


def request(method, url, json_body=None, params=None, timeout=3.0):
    """Возвращает (status_code, data). Если сервис недоступен — ServiceUnavailable."""
    params = {k: v for k, v in (params or {}).items() if v is not None}
    if _transport is not None:
        return _transport(method, url, json_body, params)

    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    body = None
    headers = {"Accept": "application/json"}
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _parse(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read())
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise ServiceUnavailable("Один из сервисов временно недоступен. Попробуйте позже.") from exc


def _parse(raw):
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return None
