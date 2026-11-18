import sqlite3
from contextlib import contextmanager
from pathlib import Path

_initialized = set()


@contextmanager
def session(path, schema):
    """Соединение с БД сервиса; схема создаётся при первом обращении к файлу."""
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        key = str(db_path.resolve())
        if key not in _initialized:
            conn.executescript(schema)
            _initialized.add(key)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
