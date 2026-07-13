from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote_plus

import psycopg2
from psycopg2.extras import RealDictCursor

from config import settings

CRM_ENV_PATH = Path(
    os.environ.get(
        "CRM_ENV_FILE",
        "C:/Users/User/Music/node/CRM COMPLETE/api-crm-admin-process/.env",
    )
)
CONNECT_TIMEOUT_SEC = int(os.environ.get("CRM_CONNECT_TIMEOUT", "5"))


def _load_env_file(path: Path) -> dict[str, str]:
    config: dict[str, str] = {}
    if not path.exists():
        return config
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip().strip('"').strip("'")
    except OSError:
        pass
    return config


def get_crm_dsn() -> str:
    """DSN del CRM: CRM_* en .env del backend, luego archivo api-crm-admin-process/.env."""
    if os.environ.get("CRM_DATABASE_URL"):
        return os.environ["CRM_DATABASE_URL"].strip()

    file_cfg = _load_env_file(CRM_ENV_PATH)

    host = (
        os.environ.get("CRM_HOST")
        or getattr(settings, "crm_host", None)
        or file_cfg.get("POSTGRES_SERVER")
        or file_cfg.get("POSTGRES_HOST")
        or "localhost"
    )
    port = (
        os.environ.get("CRM_PORT")
        or getattr(settings, "crm_port", None)
        or file_cfg.get("POSTGRES_PORT")
        or "5432"
    )
    user = (
        os.environ.get("CRM_USER")
        or getattr(settings, "crm_user", None)
        or file_cfg.get("POSTGRES_USER")
        or "postgres"
    )
    password = (
        os.environ.get("CRM_PASSWORD")
        or getattr(settings, "crm_password", None)
        or file_cfg.get("POSTGRES_PASSWORD")
        or ""
    )
    db = (
        os.environ.get("CRM_DB")
        or getattr(settings, "crm_db", None)
        or file_cfg.get("POSTGRES_DB")
        or "crm"
    )

    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{db}"
    )


@contextmanager
def get_crm_connection() -> Iterator[Any]:
    conn = psycopg2.connect(
        get_crm_dsn(),
        cursor_factory=RealDictCursor,
        connect_timeout=CONNECT_TIMEOUT_SEC,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SET statement_timeout = 15000")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_crm_all(query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    with get_crm_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


def fetch_crm_one(query: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    rows = fetch_crm_all(query, params)
    return rows[0] if rows else None
