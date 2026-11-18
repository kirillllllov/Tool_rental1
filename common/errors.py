from flask import jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    status = 400

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class ValidationError(ApiError):
    status = 400


class NotFound(ApiError):
    status = 404


class Conflict(ApiError):
    """Нарушено бизнес-правило (занят инструмент, запись используется и т.п.)."""
    status = 409


class ServiceUnavailable(ApiError):
    """Соседний микросервис не отвечает."""
    status = 503


def install(app, service_name):
    """Единый JSON-формат ошибок и /health для каждого сервиса."""
    app.json.ensure_ascii = False

    @app.errorhandler(ApiError)
    def handle_api_error(exc):
        return jsonify({"error": exc.message}), exc.status

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return jsonify({"error": exc.description}), exc.code

    @app.get("/health")
    def health():
        return jsonify({"service": service_name, "status": "ok"})
