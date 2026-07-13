from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from config import settings

logger = logging.getLogger("gptenterprice.tools")

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


def _validate_time(value: Any, field_name: str) -> str:
    import re
    value_str = str(value).strip()
    # Si viene solo la hora (ej: "9" o "09"), rellenamos con minutos
    if re.fullmatch(r"\d{1,2}", value_str):
        hour = int(value_str)
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
    # Si viene hora y minutos sin relleno (ej: "9:30"), formateamos con relleno
    if re.fullmatch(r"\d{1,2}:\d{2}", value_str):
        parts = value_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    if not re_match_time(value_str):
        raise ValueError(f"{field_name} debe estar en formato HH:MM (24h). Recibido: '{value_str}'")
    return value_str


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


def buscar_usuario(query: str, fecha: str | None = None) -> dict[str, Any]:
    _ensure_demo_db()
    if not query.strip():
        raise ValueError("query no puede estar vacío")

    target_date = fecha or date.today().isoformat()

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
        (target_date, f"%{query}%", f"%{query}%"),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not rows:
        return {
            "success": False,
            "mensaje": f"No encontré usuarios que coincidan con '{query}' en {target_date}",
        }

    return {
        "success": True,
        "resultados": rows,
        "mensaje": f"Encontré {len(rows)} usuario(s) para '{query}' el {target_date}",
    }


from tools.salescloser import (
    buscar_criterio_campana,
    buscar_llamadas,
    listar_campanas,
    listar_criterios_campana,
    listar_escalaciones,
    obtener_detalle_llamada,
    obtener_transcripcion_llamada,
    reporte_llamadas_excel,
    resumen_evaluacion_llamada,
)
from tools.salescloser_reports import (
    ejecutar_consulta_salescloser,
    exportar_excel_salescloser,
    obtener_esquema_salescloser,
)
from tools.reports import obtener_reporte_estadisticas
from tools.poster import generar_estructura_poster, generar_poster_alerta
from tools.crm import (
    ejecutar_consulta_crm,
    crm_buscar_clientes,
    crm_buscar_usuarios,
    crm_resumen_estadisticas,
)
from tools.crm_gestiones import (
    crm_listar_gestiones,
    crm_obtener_gestion,
    crm_listar_arboles_tipificacion,
    crm_arbol_capas,
    crm_listar_flujos,
    crm_buscar_items_capa,
    crm_dashboard_resumen,
)
from tools.crm_dashboard_extended import (
    crm_listar_conexiones,
    crm_dashboard_whatsapp,
    crm_dashboard_tipologico,
    crm_reporte_estados_agentes,
)

TOOL_HANDLERS = {
    # ── RRHH Demo ────────────────────────────────────────────────────────────
    "generar_reporte_excel": generar_reporte_excel,
    "buscar_usuario": buscar_usuario,
    # ── SalesCloser / Qontrol ─────────────────────────────────────────────────
    "listar_campanas": listar_campanas,
    "listar_criterios_campana": listar_criterios_campana,
    "buscar_criterio_campana": buscar_criterio_campana,
    "buscar_llamadas": buscar_llamadas,
    "obtener_transcripcion_llamada": obtener_transcripcion_llamada,
    "obtener_detalle_llamada": obtener_detalle_llamada,
    "resumen_evaluacion_llamada": resumen_evaluacion_llamada,
    "reporte_llamadas_excel": reporte_llamadas_excel,
    "obtener_esquema_salescloser": obtener_esquema_salescloser,
    "ejecutar_consulta_salescloser": ejecutar_consulta_salescloser,
    "exportar_excel_salescloser": exportar_excel_salescloser,
    "listar_escalaciones": listar_escalaciones,
    "obtener_reporte_estadisticas": obtener_reporte_estadisticas,
    # ── CRM ───────────────────────────────────────────────────────────────────
    "ejecutar_consulta_crm": ejecutar_consulta_crm,
    "crm_buscar_clientes": crm_buscar_clientes,
    "crm_buscar_usuarios": crm_buscar_usuarios,
    "crm_resumen_estadisticas": crm_resumen_estadisticas,
    "crm_listar_gestiones": crm_listar_gestiones,
    "crm_obtener_gestion": crm_obtener_gestion,
    "crm_listar_arboles_tipificacion": crm_listar_arboles_tipificacion,
    "crm_arbol_capas": crm_arbol_capas,
    "crm_listar_flujos": crm_listar_flujos,
    "crm_buscar_items_capa": crm_buscar_items_capa,
    "crm_dashboard_resumen": crm_dashboard_resumen,
    "crm_listar_conexiones": crm_listar_conexiones,
    "crm_dashboard_whatsapp": crm_dashboard_whatsapp,
    "crm_dashboard_tipologico": crm_dashboard_tipologico,
    "crm_reporte_estados_agentes": crm_reporte_estados_agentes,
    # ── Experimental ──────────────────────────────────────────────────────────
    "generar_poster_alerta": generar_poster_alerta,
    "generar_estructura_poster": generar_estructura_poster,
}

TOOL_CATALOG = {
    "generar_reporte_excel": "Demo RRHH — Excel de usuarios por rango horario",
    "buscar_usuario": "Demo RRHH — Buscar hora de entrada de un usuario",
    "listar_campanas": "SalesCloser — Listar campañas activas",
    "listar_criterios_campana": "SalesCloser — Criterios de evaluación de una campaña (por nombre, ej. BBVA)",
    "buscar_criterio_campana": "SalesCloser — Buscar criterio por título y obtener su prompt (ej. Tono de voz alta)",
    "buscar_llamadas": "SalesCloser — Buscar llamadas por fecha, campaña o cliente",
    "obtener_transcripcion_llamada": "SalesCloser — Obtener transcripción de una llamada",
    "obtener_detalle_llamada": "Qontrol — Detalle de llamada; usa seccion para un solo campo (campana, agente, score, etc.)",
    "resumen_evaluacion_llamada": "SalesCloser — Score y evaluación IA de una llamada",
    "reporte_llamadas_excel": "SalesCloser — Excel llamadas (plantilla; si el rango está vacío exporta todas)",
    "obtener_esquema_salescloser": "SalesCloser — Esquema de tablas/columnas para armar reportes SQL",
    "ejecutar_consulta_salescloser": "SalesCloser — Ejecutar SELECT de lectura (vista previa)",
    "exportar_excel_salescloser": "SalesCloser — PRINCIPAL: Excel desde SELECT personalizado (ej. solo nombres)",
    "listar_escalaciones": "SalesCloser — Ver escalaciones por estado",
    "obtener_reporte_estadisticas": "SalesCloser — Reporte agregado con estadísticas de llamadas",
    "ejecutar_consulta_crm": "CRM — Ejecutar consulta SQL SELECT personalizada en el CRM",
    "crm_buscar_clientes": "CRM — Buscar clientes por nombre, documento, ciudad o estado",
    "crm_buscar_usuarios": "CRM — Buscar usuarios/agentes del CRM",
    "crm_resumen_estadisticas": "CRM — Estadísticas globales del CRM (clientes, agentes, chats)",
    "crm_listar_gestiones": "CRM — Listar gestiones: documento=cédula, cliente=nombre, gestion_id=alias G00…",
    "crm_obtener_gestion": "CRM — Detalle y texto (text_management) de una gestión por alias G00… o UUID",
    "crm_listar_arboles_tipificacion": "CRM — Listar árboles de tipificación",
    "crm_arbol_capas": "CRM — Ver capas (catálogos) de un árbol de tipificación",
    "crm_listar_flujos": "CRM — Listar flujos nombrados de un árbol",
    "crm_buscar_items_capa": "CRM — Buscar ítems dentro de una capa del flujo",
    "crm_dashboard_resumen": "CRM — Métricas resumidas del dashboard (gestiones, clientes, agentes)",
    "crm_listar_conexiones": "CRM — Listar conexiones/canales activos",
    "crm_dashboard_whatsapp": "CRM — Dashboard WhatsApp (chats y mensajes por periodo)",
    "crm_dashboard_tipologico": "CRM — Distribución tipológica de gestiones",
    "crm_reporte_estados_agentes": "CRM — Auditoría de estados de agentes",
    "generar_poster_alerta": "[EXPERIMENTAL] Poster PNG parametrizable (colores, tamaños, secciones)",
    "generar_estructura_poster": "[EXPERIMENTAL] Igual que generar_poster_alerta (esquema estructurado)",
}


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _summarize_tool_result(name: str, result: Any) -> str:
    if not isinstance(result, dict):
        return type(result).__name__
    if name.startswith("crm_"):
        for key in ("total", "clientes", "usuarios", "gestiones", "total_registros_encontrados"):
            if key in result:
                val = result[key]
                if isinstance(val, list):
                    return f"{len(val)} filas"
                return str(val)
    if "success" in result:
        return "ok" if result.get("success") else f"fail: {result.get('error') or result.get('mensaje')}"
    return "ok"


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        logger.warning("tool desconocida: %s args=%s", name, arguments)
        return json.dumps({"success": False, "error": f"Herramienta desconocida: {name}"}, ensure_ascii=False)

    logger.info("▶ TOOL %s args=%s", name, json.dumps(arguments, ensure_ascii=False, default=str))
    try:
        result = handler(**arguments)
        summary = _summarize_tool_result(name, result)
        logger.info("✓ TOOL %s → %s", name, summary)
        return json.dumps(result, ensure_ascii=False, default=_json_default)
    except TypeError as error:
        logger.warning("✗ TOOL %s TypeError: %s", name, error)
        return json.dumps(
            {"success": False, "error": f"Parámetros inválidos para {name}: {error}"},
            ensure_ascii=False,
        )
    except ValueError as error:
        logger.warning("✗ TOOL %s ValueError: %s", name, error)
        return json.dumps({"success": False, "error": str(error)}, ensure_ascii=False)
    except Exception as error:
        logger.exception("✗ TOOL %s error: %s", name, error)
        return json.dumps({"success": False, "error": str(error)}, ensure_ascii=False)
