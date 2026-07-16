from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from config import settings
from db import fetch_all
from utils.file_urls import public_file_url

STORAGE_DIR = Path(settings.storage_dir)

READONLY_FORBIDDEN = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "replace",
    "merge",
    "call",
    "execute",
)

CORE_TABLES = (
    "calls",
    "campaigns",
    "users",
    "call_evaluations",
    "call_transcripts",
    "call_acoustics",
    "escalations",
    "supervisor_criteria",
    "prompts_config",
)

TABLE_HINTS: dict[str, str] = {
    "calls": "Llamadas. PK: id (NO usar call_id). Nombre cliente: customer_name. FK campaña: campaign_id.",
    "campaigns": "Campañas. PK: id. Nombre: name (NO campana). Activa: is_active.",
    "users": "Agentes. PK: id. Nombre: name, email.",
    "call_evaluations": "Evaluaciones IA por llamada. FK: call_id → calls.id.",
    "call_transcripts": "Transcripciones. FK: call_id → calls.id.",
    "escalations": "Escalaciones. FK: call_id → calls.id.",
    "supervisor_criteria": "Criterios de campaña. FK: campaign_id → campaigns.id. Título: title. Categoría: categoria.",
}

SQL_PATTERNS: list[dict[str, str]] = [
    {
        "caso": "Nombre de una llamada por id",
        "sql": "SELECT id, customer_name FROM calls WHERE id = 166",
    },
    {
        "caso": "Categoría de un criterio por título y campaña",
        "sql": (
            "SELECT sc.title, sc.categoria, camp.name AS campana "
            "FROM supervisor_criteria sc "
            "JOIN campaigns camp ON camp.id = sc.campaign_id "
            "WHERE sc.title ILIKE '%Tono de voz alta%' AND camp.name ILIKE '%BBVA%'"
        ),
    },
    {
        "caso": "Campañas con menos de N criterios activos",
        "sql": (
            "SELECT camp.id, camp.name, COUNT(sc.id) AS total_criterios "
            "FROM campaigns camp "
            "LEFT JOIN supervisor_criteria sc ON sc.campaign_id = camp.id AND sc.is_active = TRUE "
            "GROUP BY camp.id, camp.name "
            "HAVING COUNT(sc.id) < 10 "
            "ORDER BY total_criterios, camp.name"
        ),
    },
    {
        "caso": "JOIN llamada con campaña",
        "sql": (
            "SELECT c.id, c.customer_name, camp.name AS campana "
            "FROM calls c "
            "LEFT JOIN campaigns camp ON camp.id = c.campaign_id "
            "WHERE c.id = 166"
        ),
    },
]


def _validate_readonly_query(query_sql: str) -> str | None:
    clean = query_sql.strip()
    if not clean:
        return "La consulta SQL está vacía."
    lowered = clean.lower()
    if not lowered.startswith("select"):
        return "Solo se permiten consultas SELECT de lectura."
    if ";" in clean.rstrip().rstrip(";"):
        return "No se permiten múltiples sentencias SQL."
    if any(re.search(rf"\b{keyword}\b", lowered) for keyword in READONLY_FORBIDDEN):
        return "Operación de modificación denegada. Solo lectura."
    return None


def obtener_esquema_salescloser(tabla: str | None = None) -> dict[str, Any]:
    """
    Devuelve tablas y columnas de SalesCloser/Qontrol para que el modelo arme reportes SQL.
    """
    if tabla and str(tabla).strip():
        rows = fetch_all(
            """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name ILIKE %s
            ORDER BY table_name, ordinal_position
            LIMIT 300
            """,
            (f"%{str(tabla).strip()}%",),
        )
    else:
        rows = fetch_all(
            """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = ANY(%s)
            ORDER BY table_name, ordinal_position
            """,
            (list(CORE_TABLES),),
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        table_name = str(row.get("table_name") or "")
        grouped.setdefault(table_name, []).append(
            {
                "columna": row.get("column_name"),
                "tipo": row.get("data_type"),
                "nullable": row.get("is_nullable") == "YES",
            }
        )

    tablas = [
        {
            "nombre": name,
            "descripcion": TABLE_HINTS.get(name),
            "columnas": columns,
        }
        for name, columns in grouped.items()
    ]

    return {
        "success": True,
        "total_tablas": len(tablas),
        "tablas": tablas,
        "flujo_obligatorio": [
            "1) obtener_esquema_salescloser (esta llamada)",
            "2) ejecutar_consulta_salescloser(query_sql) — una o más consultas según el pedido",
            "3) exportar_excel_salescloser solo si piden archivo Excel",
        ],
        "patrones_sql": SQL_PATTERNS,
        "notas": [
            "calls.id es la PK de llamadas (NO existe calls.call_id).",
            "campaigns.name es el nombre de campaña (NO campaigns.campana).",
            "supervisor_criteria.categoria existe para categoría del criterio.",
            "Solo SELECT. Usa ILIKE para búsquedas por texto.",
        ],
        "mensaje": (
            f"Esquema obtenido ({len(tablas)} tabla(s)). "
            "Ahora arma SELECT con estas columnas y llama ejecutar_consulta_salescloser."
        ),
    }


def ejecutar_consulta_salescloser(query_sql: str, limite: int | str | float = 100) -> dict[str, Any]:
    """Ejecuta SELECT de solo lectura en SalesCloser y devuelve una muestra."""
    error = _validate_readonly_query(query_sql)
    if error:
        return {"success": False, "error": error}

    try:
        limite = int(float(limite))
    except (ValueError, TypeError):
        limite = 100
    limite = max(1, min(limite, 500))

    wrapped = f"SELECT * FROM ({query_sql.strip().rstrip(';')}) AS q LIMIT {limite}"
    try:
        rows = fetch_all(wrapped)
    except Exception as exc:
        err = str(exc)
        hint = (
            "Columnas comunes: calls.id (no call_id), calls.customer_name, campaigns.name. "
            "Usa obtener_esquema_salescloser(tabla='calls') antes de SQL complejo."
        )
        if "does not exist" in err.lower() or "no existe" in err.lower():
            return {"success": False, "error": f"Error SQL: {err}", "sugerencia": hint}
        return {"success": False, "error": f"Error SQL: {err}"}
    return {
        "success": True,
        "total_muestra": len(rows),
        "resultados": rows,
        "mensaje": f"Consulta OK. Mostrando {len(rows)} fila(s) de muestra.",
    }


def exportar_excel_salescloser(
    query_sql: str,
    nombre_hoja: str = "Reporte",
    nombre_archivo: str | None = None,
    limite: int | str | float = 50000,
) -> dict[str, Any]:
    """
    Ejecuta un SELECT en SalesCloser y exporta TODAS las filas a Excel.
    El modelo debe construir el SQL según lo que pida el usuario.
    """
    error = _validate_readonly_query(query_sql)
    if error:
        return {"success": False, "error": error}

    try:
        limite = int(float(limite))
    except (ValueError, TypeError):
        limite = 50000
    limite = max(1, min(limite, 50000))

    wrapped = f"SELECT * FROM ({query_sql.strip().rstrip(';')}) AS q LIMIT {limite}"
    try:
        rows = fetch_all(wrapped)
    except Exception as exc:
        return {"success": False, "error": f"Error SQL: {exc}"}

    if not rows:
        return {
            "success": False,
            "mensaje": "La consulta no devolvió filas para exportar.",
        }

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = (nombre_hoja or "Reporte")[:31]

    headers = list(rows[0].keys())
    sheet.append(headers)

    for row in rows:
        values = []
        for key in headers:
            value = row.get(key)
            if isinstance(value, datetime):
                if value.tzinfo is not None:
                    value = value.replace(tzinfo=None)
                value = value.isoformat(sep=" ", timespec="seconds")
            elif isinstance(value, (dict, list)):
                value = str(value)
            values.append(value)
        sheet.append(values)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w\-]+", "_", (nombre_archivo or "reporte_salescloser").strip())[:60]
    filename = f"{safe_name}_{stamp}.xlsx"
    filepath = STORAGE_DIR / filename
    workbook.save(filepath)

    public_url = public_file_url(filename)
    return {
        "success": True,
        "total_filas": len(rows),
        "archivo": filename,
        "url": public_url,
        "columnas": headers,
        "mensaje": f"Excel generado con {len(rows)} fila(s).",
    }
