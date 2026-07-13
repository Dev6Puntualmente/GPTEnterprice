from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from config import settings
from db import fetch_all, fetch_one

STORAGE_DIR = Path(settings.storage_dir)


def _today() -> str:
    return date.today().isoformat()


def listar_campanas(
    solo_activas: bool | str = True,
    nombre: str | None = None,
    nombre_exacto: bool | str = False,
) -> dict[str, Any]:
    if isinstance(solo_activas, str):
        solo_activas = solo_activas.lower() in ("true", "1", "yes")
    if isinstance(nombre_exacto, str):
        nombre_exacto = nombre_exacto.lower() in ("true", "1", "yes")

    conditions: list[str] = []
    params: list[Any] = []

    if solo_activas:
        conditions.append("is_active = TRUE")

    if nombre:
        if nombre_exacto:
            conditions.append("LOWER(name) = LOWER(%s)")
            params.append(nombre.strip())
        else:
            conditions.append("name ILIKE %s")
            params.append(f"%{nombre.strip()}%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT id, name, description, is_active, created_at
        FROM campaigns
        {where}
        ORDER BY name
        LIMIT 50
    """
    rows = fetch_all(query, tuple(params))

    if nombre_exacto and nombre and rows:
        case_exact = [row for row in rows if str(row.get("name", "")) == nombre.strip()]
        if case_exact:
            rows = case_exact

    filtro = f" que coinciden con '{nombre}'" if nombre else ""
    return {
        "success": True,
        "total": len(rows),
        "campanas": rows,
        "filtro_nombre": nombre,
        "filtro_exacto": nombre_exacto,
        "mensaje": f"Encontré {len(rows)} campaña(s){filtro}",
    }


def buscar_llamadas(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    campana: str | None = None,
    cliente: str | None = None,
    call_id: int | str | float | None = None,
    limite: int | str | float = 20,
) -> dict[str, Any]:
    try:
        limite = int(float(limite))
    except (ValueError, TypeError):
        limite = 20
    limite = max(1, min(limite, 100))

    if call_id is not None:
        try:
            call_id = int(float(call_id))
        except (ValueError, TypeError):
            return {"success": False, "mensaje": f"ID de llamada inválido: {call_id}"}
        row = fetch_one(
            """
            SELECT
                c.id,
                c.customer_name,
                c.campana,
                c.channel,
                c.is_flagged,
                c.created_at,
                u.name AS agente,
                u.email AS agente_email,
                camp.name AS campana_nombre
            FROM calls c
            LEFT JOIN users u ON u.id = c.agent_id
            LEFT JOIN campaigns camp ON camp.id = c.campaign_id
            WHERE c.id = %s
            """,
            (call_id,),
        )
        if not row:
            return {"success": False, "mensaje": f"No encontré la llamada {call_id}"}
        return {
            "success": True,
            "total": 1,
            "call_id": call_id,
            "llamadas": [row],
            "mensaje": f"Llamada #{call_id} encontrada",
        }

    # Lógica inteligente de fecha
    if not fecha_inicio and not fecha_fin:
        # Default a los últimos 30 días si no se indican fechas
        from datetime import timedelta
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        start = start_date.isoformat()
        end = end_date.isoformat()
    else:
        start = fecha_inicio or _today()
        end = fecha_fin or start

    conditions = [
        "c.created_at >= %s::date",
        "c.created_at < (%s::date + INTERVAL '1 day')",
    ]
    params: list[Any] = [start, end]

    if campana:
        conditions.append("(camp.name ILIKE %s OR c.campana ILIKE %s)")
        pattern = f"%{campana}%"
        params.extend([pattern, pattern])

    if cliente:
        conditions.append("c.customer_name ILIKE %s")
        params.append(f"%{cliente}%")

    params.append(limite)
    where = " AND ".join(conditions)

    query = f"""
        SELECT
            c.id,
            c.customer_name,
            c.campana,
            c.channel,
            c.is_flagged,
            c.created_at,
            u.name AS agente,
            u.email AS agente_email,
            camp.name AS campana_nombre
        FROM calls c
        LEFT JOIN users u ON u.id = c.agent_id
        LEFT JOIN campaigns camp ON camp.id = c.campaign_id
        WHERE {where}
        ORDER BY c.created_at DESC
        LIMIT %s
    """
    rows = fetch_all(query, tuple(params))
    return {
        "success": True,
        "total": len(rows),
        "fecha_inicio": start,
        "fecha_fin": end,
        "llamadas": rows,
        "mensaje": f"Encontré {len(rows)} llamada(s) entre {start} y {end}",
    }


def obtener_transcripcion_llamada(call_id: int | str | float) -> dict[str, Any]:
    try:
        call_id = int(float(call_id))
    except (ValueError, TypeError):
        return {"success": False, "mensaje": f"ID de llamada inválido: {call_id}"}

    call = fetch_one(
        """
        SELECT c.id, c.customer_name, c.created_at, ct.content AS transcript_content
        FROM calls c
        LEFT JOIN call_transcripts ct ON ct.call_id = c.id
        WHERE c.id = %s
        """,
        (call_id,),
    )
    if not call:
        return {"success": False, "mensaje": f"No encontré la llamada {call_id}"}

    transcript = call.pop("transcript_content", None)
    if transcript is None:
        call_row = fetch_one("SELECT transcript FROM calls WHERE id = %s", (call_id,))
        transcript = call_row.get("transcript") if call_row else None

    return {
        "success": True,
        "call_id": call_id,
        "llamada": call,
        "transcripcion": transcript,
        "mensaje": f"Transcripción obtenida para llamada {call_id}",
    }


def resumen_evaluacion_llamada(call_id: int | str | float) -> dict[str, Any]:
    try:
        call_id = int(float(call_id))
    except (ValueError, TypeError):
        return {"success": False, "mensaje": f"ID de llamada inválido: {call_id}"}

    row = fetch_one(
        """
        SELECT
            c.id,
            c.customer_name,
            c.ai_evaluation,
            ce.compliance_score,
            ce.data AS evaluation_data,
            c.created_at
        FROM calls c
        LEFT JOIN call_evaluations ce ON ce.call_id = c.id
        WHERE c.id = %s
        """,
        (call_id,),
    )
    if not row:
        return {"success": False, "mensaje": f"No encontré evaluación para llamada {call_id}"}

    return {
        "success": True,
        "call_id": call_id,
        "cliente": row.get("customer_name"),
        "compliance_score": row.get("compliance_score"),
        "ai_evaluation": row.get("ai_evaluation"),
        "evaluation_data": row.get("evaluation_data"),
        "mensaje": f"Evaluación obtenida para llamada {call_id}",
    }


def reporte_llamadas_excel(
    fecha_inicio: str,
    fecha_fin: str,
    campana: str | None = None,
) -> dict[str, Any]:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    result = buscar_llamadas(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        campana=campana,
        limite=500,
    )
    rows = result.get("llamadas", [])

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Llamadas"
    sheet.append(["ID", "Cliente", "Agente", "Campaña", "Canal", "Marcada", "Fecha"])

    for row in rows:
        created = row.get("created_at")
        if isinstance(created, datetime):
            created = created.isoformat()
        sheet.append(
            [
                row.get("id"),
                row.get("customer_name"),
                row.get("agente"),
                row.get("campana_nombre") or row.get("campana"),
                row.get("channel"),
                row.get("is_flagged"),
                created,
            ],
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"llamadas_{fecha_inicio}_{fecha_fin}_{stamp}.xlsx"
    filepath = STORAGE_DIR / filename
    workbook.save(filepath)

    public_url = f"{settings.public_base_url.rstrip('/')}/files/{filename}"
    return {
        "success": True,
        "total_llamadas": len(rows),
        "archivo": filename,
        "url": public_url,
        "mensaje": f"Reporte de {len(rows)} llamadas generado",
    }


def listar_escalaciones(
    estado: str = "PENDING",
    limite: int | str | float = 20,
) -> dict[str, Any]:
    try:
        limite = int(float(limite))
    except (ValueError, TypeError):
        limite = 20
    limite = max(1, min(limite, 100))
    rows = fetch_all(
        """
        SELECT
            e.id,
            e.status,
            e.level,
            e.reason,
            e.created_at,
            c.id AS call_id,
            c.customer_name,
            u.name AS iniciada_por
        FROM escalations e
        JOIN calls c ON c.id = e.call_id
        LEFT JOIN users u ON u.id = e.initiated_by_id
        WHERE e.status::text = %s
        ORDER BY e.created_at DESC
        LIMIT %s
        """,
        (estado.upper(), limite),
    )
    return {
        "success": True,
        "total": len(rows),
        "escalaciones": rows,
        "mensaje": f"Encontré {len(rows)} escalación(es) con estado {estado}",
    }
