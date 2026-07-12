"""Conexión PostgreSQL para tools de SalesCloser (schema public)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

from config import settings


@contextmanager
def get_salescloser_connection() -> Iterator[Any]:
    conn = psycopg2.connect(settings.salescloser_dsn, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    with get_salescloser_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def fetch_one(query: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None
