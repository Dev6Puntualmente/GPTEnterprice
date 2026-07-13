from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from config import settings
from db import fetch_all

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
    "calls": "Llamadas/auditorías. Claves: id, customer_name, customer_document, agent_id, campaign_id, campana, channel, is_flagged, created_at.",
    "campaigns": "Campañas. Claves: id, name, description, parent_id, is_active.",
    "users": "Agentes/usuarios. Claves: id, name, email.",
    "call_evaluations": "Evaluaciones IA. Claves: call_id, compliance_score, data.",
    "call_transcripts": "Transcripciones. Claves: call_id, content.",
    "escalations": "Escalaciones. Claves: id, call_id, status, level, reason, created_at.",
    "supervisor_criteria": "Criterios de campaña. Claves: id, campaign_id, title, prompt, weight, is_active.",
}


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
        "notas": [
            "Tabla principal de llamadas: calls (customer_name = nombre del cliente).",
            "Para campaña por nombre usa JOIN campaigns c ON c.id = calls.campaign_id.",
            "Solo SELECT; para Excel usa exportar_excel_salescloser(query_sql).",
        ],
        "mensaje": f"Esquema obtenido ({len(tablas)} tabla(s)).",
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
    rows = fetch_all(wrapped)
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

    public_url = f"{settings.public_base_url.rstrip('/')}/files/{filename}"
    return {
        "success": True,
        "total_filas": len(rows),
        "archivo": filename,
        "url": public_url,
        "columnas": headers,
        "mensaje": f"Excel generado con {len(rows)} fila(s).",
    }
