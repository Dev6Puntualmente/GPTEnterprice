from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote_plus

import psycopg2
from psycopg2.extras import RealDictCursor

from config import settings

logger = logging.getLogger("gptenterprice.crm")

CRM_ENV_PATH = Path(
    os.environ.get(
        "CRM_ENV_FILE",
        "C:/Users/User/Music/node/CRM COMPLETE/api-crm-admin-process/.env",
    )
)
CONNECT_TIMEOUT_SEC = int(os.environ.get("CRM_CONNECT_TIMEOUT", "5"))

# is_online es enum crm.user_online_status (texto), no boolean.
USERS_ONLINE_CONDITION = (
    "is_active = TRUE AND UPPER(COALESCE(is_online::text, 'OFFLINE')) = 'ONLINE'"
)


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


def get_crm_connection_info() -> dict[str, str]:
    """Metadatos de conexión sin exponer la contraseña."""
    if os.environ.get("CRM_DATABASE_URL"):
        return {"source": "CRM_DATABASE_URL", "host": "(url)", "port": "", "db": "", "user": ""}

    file_cfg = _load_env_file(CRM_ENV_PATH)
    host = (
        os.environ.get("CRM_HOST")
        or getattr(settings, "crm_host", None)
        or file_cfg.get("POSTGRES_SERVER")
        or file_cfg.get("POSTGRES_HOST")
        or "localhost"
    )
    port = str(
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
    db = (
        os.environ.get("CRM_DB")
        or getattr(settings, "crm_db", None)
        or file_cfg.get("POSTGRES_DB")
        or "crm"
    )
    source = "backend/.env" if os.environ.get("CRM_HOST") else (
        str(CRM_ENV_PATH) if file_cfg else "defaults"
    )
    return {
        "source": source,
        "host": str(host),
        "port": port,
        "db": str(db),
        "user": str(user),
    }


def crm_error_hint(error: Exception) -> str:
    message = str(error).lower()
    if "timeout" in message or "timed out" in message:
        return (
            "No hubo respuesta a tiempo. Verifica VPN/red hacia el servidor CRM "
            f"o aumenta CRM_CONNECT_TIMEOUT (actual {CONNECT_TIMEOUT_SEC}s)."
        )
    if "connection refused" in message or "could not connect" in message:
        return "El host/puerto no acepta conexiones. Revisa CRM_HOST, CRM_PORT y firewall."
    if "password authentication failed" in message:
        return "Usuario o contraseña incorrectos. Configura CRM_USER y CRM_PASSWORD en backend/.env."
    if "permission denied" in message or "insufficientprivilege" in message:
        return (
            "El usuario PostgreSQL necesita SELECT en los schemas crm, config y whatsapp. "
            "No es permiso JWT de la API — es rol de base de datos."
        )
    if "does not exist" in message and "database" in message:
        return "La base de datos CRM_DB no existe en ese servidor."
    return "Revisa CRM_HOST, CRM_PORT, CRM_USER, CRM_PASSWORD y CRM_DB en backend/.env."


def test_crm_connection() -> dict[str, Any]:
    """Prueba conectividad y permisos mínimos de lectura al CRM."""
    info = get_crm_connection_info()
    try:
        with get_crm_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 AS ok")
                cursor.execute("SELECT COUNT(*) AS total FROM crm.clients")
                clients = cursor.fetchone()
                cursor.execute(
                    "SELECT COUNT(*) AS total FROM crm.management_history WHERE is_active = TRUE"
                )
                gestiones = cursor.fetchone()
        return {
            "success": True,
            "connection": info,
            "samples": {
                "clientes": clients.get("total") if clients else 0,
                "gestiones_activas": gestiones.get("total") if gestiones else 0,
            },
            "mensaje": "Conexión CRM OK.",
        }
    except Exception as error:
        return {
            "success": False,
            "connection": info,
            "error": str(error),
            "hint": crm_error_hint(error),
        }


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
    preview = " ".join(query.split())[:220]
    logger.info("CRM SQL → %s | params=%s", preview, params)
    with get_crm_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            logger.info("CRM SQL ← %s filas", len(result))
            return result


def fetch_crm_one(query: str, params: tuple[Any, ...] | None = None) -> dict[str, Any] | None:
    rows = fetch_crm_all(query, params)
    return rows[0] if rows else None
