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


def _parse_call_id(call_id: int | str | float) -> int | None:
    try:
        return int(float(call_id))
    except (ValueError, TypeError):
        return None


def _merge_ai_evaluation(row: dict[str, Any]) -> dict[str, Any] | None:
    legacy = row.get("ai_evaluation")
    if isinstance(legacy, str):
        import json

        try:
            legacy = json.loads(legacy)
        except json.JSONDecodeError:
            legacy = None
    computed = row.get("evaluation_data")
    if isinstance(computed, str):
        import json

        try:
            computed = json.loads(computed)
        except json.JSONDecodeError:
            computed = None
    if isinstance(computed, dict):
        ai = dict(computed)
    elif isinstance(legacy, dict):
        ai = dict(legacy)
    else:
        ai = {}
    if row.get("compliance_score") is not None and "compliance_score" not in ai:
        ai["compliance_score"] = row.get("compliance_score")
    return ai or None


def _normalize_transcript(row: dict[str, Any]) -> list[dict[str, Any]]:
    transcript = row.get("transcript_content") or row.get("transcript")
    if isinstance(transcript, str):
        import json

        try:
            transcript = json.loads(transcript)
        except json.JSONDecodeError:
            return [{"speaker": "N/D", "text": transcript}]
    if isinstance(transcript, list):
        return [seg for seg in transcript if isinstance(seg, dict)]
    return []


def _normalize_acoustic(row: dict[str, Any]) -> dict[str, Any] | None:
    acoustic = row.get("acoustic_table") or row.get("acoustic_analysis")
    if isinstance(acoustic, str):
        import json

        try:
            acoustic = json.loads(acoustic)
        except json.JSONDecodeError:
            return None
    return acoustic if isinstance(acoustic, dict) else None


def _criterion_status_label(result: dict[str, Any]) -> str:
    if not result.get("applicable", True):
        return "No aplica"
    if result.get("pass") == 1:
        return "Cumplido"
    if result.get("pass") == 0:
        return "No cumplido"
    return "Pendiente"


def obtener_detalle_llamada(
    call_id: int | str | float,
    seccion: str | None = None,
    limite_transcripcion: int | str | float = 40,
) -> dict[str, Any]:
    """
    Detalle completo de una llamada/auditoría Qontrol (equivalente a CallDetail):
    cabecera, score, resumen IA, criterios, acústica, transcripción o chat WhatsApp.
    """
    parsed_id = _parse_call_id(call_id)
    if parsed_id is None:
        return {"success": False, "mensaje": f"ID de llamada inválido: {call_id}"}

    try:
        limite_transcripcion = int(float(limite_transcripcion))
    except (ValueError, TypeError):
        limite_transcripcion = 40
    limite_transcripcion = max(5, min(limite_transcripcion, 200))

    row = fetch_one(
        """
        SELECT
            c.id,
            c.customer_name,
            c.customer_document,
            c.campana,
            c.channel,
            c.audio_url,
            c.is_flagged,
            c.created_at,
            c.ai_evaluation,
            c.acoustic_analysis,
            c.transcript,
            c.selected_criteria,
            c.coaching_items,
            c.human_calibration,
            c.source_metadata,
            u.name AS agent_name,
            u.email AS agent_email,
            camp.name AS campana_nombre,
            ce.compliance_score,
            ce.data AS evaluation_data,
            ce.updated_at AS audited_at,
            ct.content AS transcript_content,
            ca.analysis AS acoustic_table
        FROM calls c
        LEFT JOIN users u ON u.id = c.agent_id
        LEFT JOIN campaigns camp ON camp.id = c.campaign_id
        LEFT JOIN call_evaluations ce ON ce.call_id = c.id
        LEFT JOIN call_transcripts ct ON ct.call_id = c.id
        LEFT JOIN call_acoustics ca ON ca.call_id = c.id
        WHERE c.id = %s
        """,
        (parsed_id,),
    )
    if not row:
        return {"success": False, "mensaje": f"No encontré la llamada {parsed_id}"}

    ai = _merge_ai_evaluation(row) or {}
    human = row.get("human_calibration")
    if isinstance(human, str):
        import json

        try:
            human = json.loads(human)
        except json.JSONDecodeError:
            human = None

    human_score = None
    if isinstance(human, dict):
        human_score = human.get("humanScore")
        if human_score is None:
            human_score = human.get("human_score")
    effective_score = human_score if human_score is not None else ai.get("compliance_score")
    score_label = "Score H" if human_score is not None else "Score IA"

    source_meta = row.get("source_metadata")
    if isinstance(source_meta, str):
        import json

        try:
            source_meta = json.loads(source_meta)
        except json.JSONDecodeError:
            source_meta = {}
    source_meta = source_meta if isinstance(source_meta, dict) else {}

    channel = (row.get("channel") or "llamada").lower()
    transcript_segments = _normalize_transcript(row)
    chat_messages = source_meta.get("chatMessages")
    if not isinstance(chat_messages, list):
        chat_messages = []

    criteria_results = ai.get("criteria_results") if isinstance(ai.get("criteria_results"), list) else []
    selected_criteria = row.get("selected_criteria")
    if isinstance(selected_criteria, str):
        import json

        try:
            selected_criteria = json.loads(selected_criteria)
        except json.JSONDecodeError:
            selected_criteria = []
    if not isinstance(selected_criteria, list):
        selected_criteria = []

    passed = sum(1 for c in criteria_results if c.get("applicable", True) and c.get("pass") == 1)
    failed = sum(1 for c in criteria_results if c.get("applicable", True) and c.get("pass") == 0)

    acoustic = _normalize_acoustic(row)
    callgist = ai.get("callgist_comparison") if isinstance(ai.get("callgist_comparison"), dict) else None

    detalle = {
        "cabecera": {
            "id": parsed_id,
            "cliente": row.get("customer_name"),
            "documento_cliente": row.get("customer_document") or ai.get("customer_document"),
            "agente": row.get("agent_name") or ai.get("resolved_agent_name"),
            "documento_agente": ai.get("agent_document") or source_meta.get("agentDocument"),
            "campana": row.get("campana_nombre") or row.get("campana"),
            "canal": channel,
            "marcada": bool(row.get("is_flagged")),
            "fecha_llamada": ai.get("audio_call_date"),
            "fecha_auditoria": row.get("audited_at") or row.get("created_at"),
            "fecha_registro": row.get("created_at"),
        },
        "score": {
            "valor": effective_score,
            "etiqueta": score_label,
            "sentimiento": ai.get("sentiment"),
            "calibrado": human_score is not None,
            "human_score": human_score,
            "ai_score": ai.get("compliance_score"),
        },
        "resumen": {
            "texto": ai.get("summary"),
            "preview_transcripcion": ai.get("transcript_preview"),
            "momentos_clave": ai.get("key_moments") or [],
            "metodo_transcripcion": ai.get("transcript_method"),
        },
        "callgist": callgist,
        "criterios": {
            "total_seleccionados": len(selected_criteria),
            "total_evaluados": len(criteria_results),
            "cumplidos": passed,
            "no_cumplidos": failed,
            "resultados": [
                {
                    "criterion_id": item.get("criterionId"),
                    "titulo": item.get("title"),
                    "estado": _criterion_status_label(item),
                    "peso": item.get("weight"),
                    "eval_kind": item.get("evalKind"),
                    "justificacion": item.get("justification"),
                    "evidencia": item.get("evidence"),
                    "inicio_seg": item.get("start"),
                }
                for item in criteria_results[:30]
            ],
        },
        "acustica": acoustic,
        "transcripcion": {
            "total_segmentos": len(transcript_segments),
            "segmentos": transcript_segments[:limite_transcripcion],
            "truncada": len(transcript_segments) > limite_transcripcion,
        },
        "chat_whatsapp": {
            "total_mensajes": len(chat_messages),
            "mensajes": chat_messages[:50],
            "metricas": source_meta.get("chatMetrics"),
            "truncado": len(chat_messages) > 50,
        },
        "coaching": row.get("coaching_items") or [],
    }

    seccion_norm = (seccion or "completo").strip().lower()
    if seccion_norm not in ("completo", "resumen", "criterios", "transcripcion", "chat", "acustica", "callgist"):
        seccion_norm = "completo"

    payload: dict[str, Any] = {
        "success": True,
        "call_id": parsed_id,
        "seccion": seccion_norm,
        "detalle": detalle,
        "mensaje": f"Detalle de llamada #{parsed_id} obtenido",
    }

    if seccion_norm == "resumen":
        payload["detalle"] = {
            "cabecera": detalle["cabecera"],
            "score": detalle["score"],
            "resumen": detalle["resumen"],
        }
    elif seccion_norm == "criterios":
        payload["detalle"] = {"cabecera": detalle["cabecera"], "criterios": detalle["criterios"]}
    elif seccion_norm == "transcripcion":
        payload["detalle"] = {
            "cabecera": detalle["cabecera"],
            "transcripcion": detalle["transcripcion"],
        }
    elif seccion_norm == "chat":
        payload["detalle"] = {"cabecera": detalle["cabecera"], "chat_whatsapp": detalle["chat_whatsapp"]}
    elif seccion_norm == "acustica":
        payload["detalle"] = {"cabecera": detalle["cabecera"], "acustica": detalle["acustica"]}
    elif seccion_norm == "callgist":
        payload["detalle"] = {"cabecera": detalle["cabecera"], "callgist": detalle["callgist"]}

    return payload


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
