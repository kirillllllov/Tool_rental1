"""Запуск всей системы локально одной командой (без Docker): python run_local.py

Поднимает четыре микросервиса и веб-интерфейс на соседних портах:
  web :5000, tools :5001, customers :5002, rentals :5003, maintenance :5004
Каждый сервис использует свою SQLite-базу в instance/ внутри своей папки.
"""
import sys
import threading
from importlib import import_module
from pathlib import Path

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parent
SERVICES = [("tools", 5001), ("customers", 5002), ("rentals", 5003), ("maintenance", 5004), ("web", 5000)]

sys.path.insert(0, str(ROOT))
for name, _ in SERVICES:
    sys.path.insert(0, str(ROOT / "services" / name))


def main():
    servers = []
    for name, port in SERVICES:
        module = import_module(f"{name}_app")
        server = make_server("127.0.0.1", port, module.app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True, name=name).start()
        servers.append(server)
        print(f"  {name:12s} http://127.0.0.1:{port}")
    print("\nОткройте http://127.0.0.1:5000  (Ctrl+C — остановить)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        for server in servers:
            server.shutdown()


if __name__ == "__main__":
    main()
