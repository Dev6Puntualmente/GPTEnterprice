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


def listar_campanas(solo_activas: bool = True) -> dict[str, Any]:
    if solo_activas:
        query = """
            SELECT id, name, description, is_active, created_at
            FROM campaigns
            WHERE is_active = TRUE
            ORDER BY name
            LIMIT 50
        """
        rows = fetch_all(query)
    else:
        query = """
            SELECT id, name, description, is_active, created_at
            FROM campaigns
            ORDER BY name
            LIMIT 50
        """
        rows = fetch_all(query)

    return {
        "success": True,
        "total": len(rows),
        "campanas": rows,
        "mensaje": f"Encontré {len(rows)} campaña(s)",
    }


def buscar_llamadas(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    campana: str | None = None,
    cliente: str | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    limite = max(1, min(limite, 100))
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


def obtener_transcripcion_llamada(call_id: int) -> dict[str, Any]:
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


def resumen_evaluacion_llamada(call_id: int) -> dict[str, Any]:
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


def listar_escalaciones(estado: str = "PENDING", limite: int = 20) -> dict[str, Any]:
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
