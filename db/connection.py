import json
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

_config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")


def _load_db_config():
    with open(_config_path) as f:
        return json.load(f)["database"]


@contextmanager
def get_connection():
    cfg = _load_db_config()
    conn = psycopg2.connect(**cfg)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(conn):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
    finally:
        cur.close()
