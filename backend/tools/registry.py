from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from config import settings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "demo.db"
STORAGE_DIR = Path(settings.storage_dir)


def _ensure_demo_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            hora_entrada TEXT NOT NULL,
            fecha TEXT NOT NULL,
            departamento TEXT NOT NULL
        )
        """
    )

    today = date.today().isoformat()
    sample_rows = [
        ("U001", "Ana García", "08:15", today, "Ventas"),
        ("U002", "Carlos Ruiz", "09:02", today, "Soporte"),
        ("U003", "María López", "11:30", today, "RRHH"),
        ("U004", "Pedro Sánchez", "13:45", today, "Ventas"),
        ("U005", "Laura Méndez", "16:10", today, "Marketing"),
        ("U006", "Diego Torres", "07:50", today, "Operaciones"),
        ("U007", "Sofia Herrera", "12:05", today, "Ventas"),
        ("U008", "Juan Pérez", "14:20", today, "Soporte"),
    ]
    cursor.executemany(
        "INSERT INTO users (id, nombre, hora_entrada, fecha, departamento) VALUES (?, ?, ?, ?, ?)",
        sample_rows,
    )
    conn.commit()
    conn.close()


def _validate_time(value: str, field_name: str) -> str:
    if not re_match_time(value):
        raise ValueError(f"{field_name} debe estar en formato HH:MM (24h)")
    return value


def re_match_time(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value))


def generar_reporte_excel(
    hora_inicio: str,
    hora_fin: str,
    fecha: str | None = None,
) -> dict[str, Any]:
    _ensure_demo_db()
    hora_inicio = _validate_time(hora_inicio, "hora_inicio")
    hora_fin = _validate_time(hora_fin, "hora_fin")
    target_date = fecha or date.today().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, nombre, hora_entrada, fecha, departamento
        FROM users
        WHERE fecha = ? AND hora_entrada BETWEEN ? AND ?
        ORDER BY hora_entrada
        """,
        (target_date, hora_inicio, hora_fin),
    )
    rows = cursor.fetchall()
    conn.close()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Usuarios"
    sheet.append(["ID", "Nombre", "Hora entrada", "Fecha", "Departamento"])
    for row in rows:
        sheet.append([row["id"], row["nombre"], row["hora_entrada"], row["fecha"], row["departamento"]])

    filename = f"reporte_{target_date}_{hora_inicio.replace(':', '')}_{hora_fin.replace(':', '')}.xlsx"
    filepath = STORAGE_DIR / filename
    workbook.save(filepath)

    public_url = f"{settings.public_base_url.rstrip('/')}/files/{filename}"
    return {
        "success": True,
        "total_usuarios": len(rows),
        "fecha": target_date,
        "hora_inicio": hora_inicio,
        "hora_fin": hora_fin,
        "archivo": filename,
        "url": public_url,
        "mensaje": f"Reporte generado con {len(rows)} usuarios entre {hora_inicio} y {hora_fin}",
    }


def buscar_usuario(query: str, fecha: str) -> dict[str, Any]:
    _ensure_demo_db()
    if not query.strip():
        raise ValueError("query no puede estar vacío")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, nombre, hora_entrada, fecha, departamento
        FROM users
        WHERE fecha = ? AND (id LIKE ? OR nombre LIKE ?)
        ORDER BY nombre
        LIMIT 5
        """,
        (fecha, f"%{query}%", f"%{query}%"),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not rows:
        return {
            "success": False,
            "mensaje": f"No encontré usuarios que coincidan con '{query}' en {fecha}",
        }

    return {
        "success": True,
        "resultados": rows,
        "mensaje": f"Encontré {len(rows)} usuario(s) para '{query}' el {fecha}",
    }


TOOL_HANDLERS = {
    "generar_reporte_excel": generar_reporte_excel,
    "buscar_usuario": buscar_usuario,
}


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return json.dumps({"success": False, "error": f"Herramienta desconocida: {name}"}, ensure_ascii=False)

    try:
        result = handler(**arguments)
        return json.dumps(result, ensure_ascii=False)
    except TypeError as error:
        return json.dumps(
            {"success": False, "error": f"Parámetros inválidos para {name}: {error}"},
            ensure_ascii=False,
        )
    except ValueError as error:
        return json.dumps({"success": False, "error": str(error)}, ensure_ascii=False)
    except Exception as error:
        return json.dumps({"success": False, "error": str(error)}, ensure_ascii=False)
