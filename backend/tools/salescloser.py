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


def _normalize_detalle_seccion(seccion: str | None) -> str:
    if not seccion:
        return "completo"
    raw = seccion.strip().lower()
    aliases = {
        "campaña": "campana",
        "campaign": "campana",
        "customer": "cliente",
        "agent": "agente",
        "puntuacion": "score",
        "puntuación": "score",
        "compliance": "score",
        "channel": "canal",
        "fecha_llamada": "fecha",
        "fecha_auditoria": "fecha",
        "documento_cliente": "documento",
        "marcada": "marcada",
        "flagged": "marcada",
    }
    return aliases.get(raw, raw)


def _build_field_payload(
    seccion: str,
    *,
    parsed_id: int,
    row: dict[str, Any],
    ai: dict[str, Any],
    effective_score: Any,
    score_label: str,
    channel: str,
    human_score: Any,
) -> dict[str, Any] | None:
    campana = row.get("campana_nombre") or row.get("campana")
    agente = row.get("agent_name") or ai.get("resolved_agent_name")
    if seccion == "campana":
        return {"success": True, "call_id": parsed_id, "seccion": seccion, "campana": campana}
    if seccion == "cliente":
        return {
            "success": True,
            "call_id": parsed_id,
            "seccion": seccion,
            "cliente": row.get("customer_name"),
        }
    if seccion == "agente":
        return {"success": True, "call_id": parsed_id, "seccion": seccion, "agente": agente}
    if seccion == "score":
        return {
            "success": True,
            "call_id": parsed_id,
            "seccion": seccion,
            "score": effective_score,
            "etiqueta": score_label,
            "sentimiento": ai.get("sentiment"),
            "calibrado": human_score is not None,
        }
    if seccion == "canal":
        return {"success": True, "call_id": parsed_id, "seccion": seccion, "canal": channel}
    if seccion == "documento":
        return {
            "success": True,
            "call_id": parsed_id,
            "seccion": seccion,
            "documento": row.get("customer_document") or ai.get("customer_document"),
        }
    if seccion == "fecha":
        return {
            "success": True,
            "call_id": parsed_id,
            "seccion": seccion,
            "fecha_llamada": ai.get("audio_call_date"),
            "fecha_auditoria": row.get("audited_at") or row.get("created_at"),
            "fecha_registro": row.get("created_at"),
        }
    if seccion == "marcada":
        return {
            "success": True,
            "call_id": parsed_id,
            "seccion": seccion,
            "marcada": bool(row.get("is_flagged")),
        }
    if seccion == "cabecera":
        return {
            "success": True,
            "call_id": parsed_id,
            "seccion": seccion,
            "cliente": row.get("customer_name"),
            "documento": row.get("customer_document") or ai.get("customer_document"),
            "agente": agente,
            "campana": campana,
            "canal": channel,
            "marcada": bool(row.get("is_flagged")),
            "fecha_llamada": ai.get("audio_call_date"),
            "fecha_auditoria": row.get("audited_at") or row.get("created_at"),
            "fecha_registro": row.get("created_at"),
        }
    return None


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

    seccion_norm = _normalize_detalle_seccion(seccion)
    field_payload = _build_field_payload(
        seccion_norm,
        parsed_id=parsed_id,
        row=row,
        ai=ai,
        effective_score=effective_score,
        score_label=score_label,
        channel=channel,
        human_score=human_score,
    )
    if field_payload is not None:
        return field_payload

    allowed_sections = (
        "completo",
        "resumen",
        "criterios",
        "transcripcion",
        "chat",
        "acustica",
        "callgist",
    )
    if seccion_norm not in allowed_sections:
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


EXPORT_COLUMN_ALIASES: dict[str, tuple[str, str]] = {
    "id": ("c.id", "ID"),
    "customer_name": ("c.customer_name", "Nombre"),
    "nombre": ("c.customer_name", "Nombre"),
    "cliente": ("c.customer_name", "Cliente"),
    "customer_document": ("c.customer_document", "Documento"),
    "campana": ("COALESCE(camp.name, c.campana)", "Campaña"),
    "campaign_id": ("c.campaign_id", "Campaña ID"),
    "channel": ("c.channel", "Canal"),
    "is_flagged": ("c.is_flagged", "Marcada"),
    "created_at": ("c.created_at", "Fecha"),
    "agente": ("u.name", "Agente"),
    "agent_id": ("c.agent_id", "Agente ID"),
}


def _parse_bool_export(value: bool | str, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "si", "sí")
    return default


def _normalize_export_columnas(columnas: list[str] | str | None) -> list[str]:
    if columnas is None:
        return ["id", "customer_name", "agente", "campana", "channel", "is_flagged", "created_at"]
    if isinstance(columnas, str):
        import json

        text = columnas.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item).lower().strip() for item in parsed]
            except json.JSONDecodeError:
                pass
        return [part.lower().strip() for part in text.split(",") if part.strip()]
    return [str(item).lower().strip() for item in columnas]


def _fetch_calls_for_excel(
    *,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    campana: str | None = None,
    columnas: list[str] | str | None = None,
    todas: bool = False,
    limite: int = 50000,
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    requested = _normalize_export_columnas(columnas)
    select_parts: list[str] = []
    headers: list[str] = []
    for key in requested:
        mapping = EXPORT_COLUMN_ALIASES.get(key)
        if not mapping:
            continue
        expr, label = mapping
        select_parts.append(f'{expr} AS "{label}"')
        headers.append(label)
    if not select_parts:
        select_parts = [
            'c.id AS "ID"',
            'c.customer_name AS "Nombre"',
            'u.name AS "Agente"',
            'COALESCE(camp.name, c.campana) AS "Campaña"',
            'c.channel AS "Canal"',
            'c.is_flagged AS "Marcada"',
            'c.created_at AS "Fecha"',
        ]
        headers = ["ID", "Nombre", "Agente", "Campaña", "Canal", "Marcada", "Fecha"]

    conditions: list[str] = []
    params: list[Any] = []
    use_dates = not todas and bool(fecha_inicio or fecha_fin)
    if use_dates:
        start = (fecha_inicio or fecha_fin or _today()).strip()
        end = (fecha_fin or fecha_inicio or start).strip()
        conditions.extend(
            [
                "c.created_at >= %s::date",
                "c.created_at < (%s::date + INTERVAL '1 day')",
            ]
        )
        params.extend([start, end])

    if campana:
        conditions.append("(camp.name ILIKE %s OR c.campana ILIKE %s)")
        pattern = f"%{campana.strip()}%"
        params.extend([pattern, pattern])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT {", ".join(select_parts)}
        FROM calls c
        LEFT JOIN users u ON u.id = c.agent_id
        LEFT JOIN campaigns camp ON camp.id = c.campaign_id
        {where}
        ORDER BY c.created_at DESC
        LIMIT %s
    """
    params.append(limite)
    rows = fetch_all(query, tuple(params))

    aviso: str | None = None
    if not rows and use_dates:
        fallback_conditions: list[str] = []
        fallback_params: list[Any] = []
        if campana:
            fallback_conditions.append("(camp.name ILIKE %s OR c.campana ILIKE %s)")
            pattern = f"%{campana.strip()}%"
            fallback_params.extend([pattern, pattern])
        fallback_where = (
            f"WHERE {' AND '.join(fallback_conditions)}" if fallback_conditions else ""
        )
        fallback_query = f"""
            SELECT {", ".join(select_parts)}
            FROM calls c
            LEFT JOIN users u ON u.id = c.agent_id
            LEFT JOIN campaigns camp ON camp.id = c.campaign_id
            {fallback_where}
            ORDER BY c.created_at DESC
            LIMIT %s
        """
        fallback_params.append(limite)
        rows = fetch_all(fallback_query, tuple(fallback_params))
        if rows:
            aviso = (
                f"No había llamadas entre {fecha_inicio} y {fecha_fin}; "
                f"se exportaron todas las llamadas disponibles ({len(rows)})."
            )

    return rows, headers, aviso


def _excel_cell_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.replace(tzinfo=None)
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, (dict, list)):
        return str(value)
    return value


def reporte_llamadas_excel(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    campana: str | None = None,
    columnas: list[str] | str | None = None,
    todas: bool | str = False,
) -> dict[str, Any]:
    """
    Exporta llamadas a Excel. Si no hay datos en el rango de fechas, reintenta con todas las llamadas.
    Para reportes SQL personalizados preferir exportar_excel_salescloser.
    """
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    export_all = _parse_bool_export(todas, False) or (not fecha_inicio and not fecha_fin)

    rows, headers, aviso = _fetch_calls_for_excel(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        campana=campana,
        columnas=columnas,
        todas=export_all,
    )

    if not rows:
        return {
            "success": False,
            "total_llamadas": 0,
            "mensaje": (
                "No encontré llamadas para exportar. "
                "Prueba sin fechas, con todas=true, o usa exportar_excel_salescloser."
            ),
        }

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Llamadas"
    sheet.append(headers)

    for row in rows:
        sheet.append([_excel_cell_value(row.get(header)) for header in headers])

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    range_label = "todas" if export_all else f"{fecha_inicio or 'inicio'}_{fecha_fin or 'fin'}"
    filename = f"llamadas_{range_label}_{stamp}.xlsx"
    filepath = STORAGE_DIR / filename
    workbook.save(filepath)

    public_url = f"{settings.public_base_url.rstrip('/')}/files/{filename}"
    mensaje = f"Reporte de {len(rows)} llamada(s) generado"
    if aviso:
        mensaje = f"{mensaje}. {aviso}"
    return {
        "success": True,
        "total_llamadas": len(rows),
        "archivo": filename,
        "url": public_url,
        "columnas": headers,
        "mensaje": mensaje,
        "aviso": aviso,
    }


def _criterion_key(title: str, prompt: str) -> str:
    return f"{title.strip().lower()}|{prompt.strip().lower()}"


def _parse_bool(value: bool | str, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "si", "sí")
    return default


def _resolve_campaign(
    campana: str | None = None,
    campana_id: int | str | float | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if campana_id is not None:
        try:
            parsed_id = int(float(campana_id))
        except (ValueError, TypeError):
            return None, []
        row = fetch_one(
            """
            SELECT id, name, description, parent_id, inherits_parent_criteria, is_active
            FROM campaigns
            WHERE id = %s
            """,
            (parsed_id,),
        )
        return row, []

    if not campana or not str(campana).strip():
        return None, []

    name = str(campana).strip()
    exact = fetch_one(
        """
        SELECT id, name, description, parent_id, inherits_parent_criteria, is_active
        FROM campaigns
        WHERE LOWER(name) = LOWER(%s)
        """,
        (name,),
    )
    if exact:
        return exact, []

    candidates = fetch_all(
        """
        SELECT id, name, description, parent_id, inherits_parent_criteria, is_active
        FROM campaigns
        WHERE name ILIKE %s
        ORDER BY is_active DESC, name
        LIMIT 10
        """,
        (f"%{name}%",),
    )
    if len(candidates) == 1:
        return candidates[0], []
    return None, candidates


def _fetch_own_criteria_rows(campaign_id: int, active_only: bool = True) -> list[dict[str, Any]]:
    conditions = ["sc.campaign_id = %s"]
    params: list[Any] = [campaign_id]
    if active_only:
        conditions.append("sc.is_active = TRUE")

    query = f"""
        SELECT
            sc.id,
            sc.campaign_id,
            sc.title,
            sc.prompt,
            sc.weight,
            sc.is_active,
            sc.non_applicable_hint,
            sc.tipo,
            sc.categoria,
            sc.eval_kind,
            sc.is_important,
            sc.channels,
            camp.name AS campana_nombre
        FROM supervisor_criteria sc
        JOIN campaigns camp ON camp.id = sc.campaign_id
        WHERE {' AND '.join(conditions)}
        ORDER BY sc.title ASC, sc.id ASC
    """
    return fetch_all(query, tuple(params))


def _fetch_effective_campaign_criteria(
    campaign_id: int,
    active_only: bool = True,
    include_inherited: bool = True,
    _visited: set[int] | None = None,
) -> list[dict[str, Any]]:
    if _visited is None:
        _visited = set()
    if campaign_id in _visited:
        return []
    _visited.add(campaign_id)

    campaign = fetch_one(
        """
        SELECT id, name, parent_id, inherits_parent_criteria
        FROM campaigns
        WHERE id = %s
        """,
        (campaign_id,),
    )
    if not campaign:
        return []

    own = _fetch_own_criteria_rows(campaign_id, active_only)
    for row in own:
        row["origen"] = "propio"

    parent_id = campaign.get("parent_id")
    inherits_parent = campaign.get("inherits_parent_criteria") is not False
    if not include_inherited or not parent_id or not inherits_parent:
        return own

    parent_criteria = _fetch_effective_campaign_criteria(
        int(parent_id),
        active_only=active_only,
        include_inherited=True,
        _visited=_visited,
    )
    own_keys = {_criterion_key(str(c.get("title", "")), str(c.get("prompt", ""))) for c in own}
    inherited: list[dict[str, Any]] = []
    for criterion in parent_criteria:
        key = _criterion_key(str(criterion.get("title", "")), str(criterion.get("prompt", "")))
        if key in own_keys:
            continue
        inherited.append({**criterion, "origen": "heredado"})
    return inherited + own


def _serialize_criterion(row: dict[str, Any], include_prompt: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row.get("id"),
        "titulo": row.get("title"),
        "campana_id": row.get("campaign_id"),
        "campana": row.get("campana_nombre"),
        "peso": row.get("weight"),
        "activo": row.get("is_active"),
        "tipo": row.get("tipo"),
        "categoria": row.get("categoria"),
        "eval_kind": row.get("eval_kind"),
        "importante": row.get("is_important"),
        "canales": row.get("channels"),
        "hint_no_aplica": row.get("non_applicable_hint"),
        "origen": row.get("origen", "propio"),
    }
    if include_prompt:
        payload["prompt"] = row.get("prompt")
    return payload


def listar_criterios_campana(
    campana: str | None = None,
    campana_id: int | str | float | None = None,
    incluir_heredados: bool | str = True,
    solo_activos: bool | str = True,
    incluir_prompt: bool | str = False,
) -> dict[str, Any]:
    """
    Lista criterios de evaluación de una campaña Qontrol (supervisor_criteria).
    Busca la campaña por nombre (ej. BBVA) o por campana_id.
    """
    active_only = _parse_bool(solo_activos, True)
    include_inherited = _parse_bool(incluir_heredados, True)
    with_prompt = _parse_bool(incluir_prompt, False)

    campaign, candidates = _resolve_campaign(campana=campana, campana_id=campana_id)
    if not campaign:
        if candidates:
            return {
                "success": False,
                "mensaje": f"Hay varias campañas que coinciden con '{campana}'. Sé más específico.",
                "candidatos": [
                    {"id": row.get("id"), "nombre": row.get("name"), "activa": row.get("is_active")}
                    for row in candidates
                ],
            }
        label = campana or campana_id
        return {"success": False, "mensaje": f"No encontré la campaña '{label}'"}

    rows = _fetch_effective_campaign_criteria(
        int(campaign["id"]),
        active_only=active_only,
        include_inherited=include_inherited,
    )
    criterios = [_serialize_criterion(row, include_prompt=with_prompt) for row in rows]
    return {
        "success": True,
        "campana": {
            "id": campaign.get("id"),
            "nombre": campaign.get("name"),
            "activa": campaign.get("is_active"),
            "hereda_criterios_padre": campaign.get("inherits_parent_criteria") is not False,
        },
        "total": len(criterios),
        "incluye_heredados": include_inherited,
        "criterios": criterios,
        "mensaje": (
            f"Encontré {len(criterios)} criterio(s) para la campaña "
            f"'{campaign.get('name')}'"
        ),
    }


def buscar_criterio_campana(
    nombre: str,
    campana: str | None = None,
    solo_activos: bool | str = True,
) -> dict[str, Any]:
    """
    Busca un criterio de campaña por nombre/título (ej. 'Tono de voz alta')
    y devuelve su prompt completo. Filtro opcional por campaña.
    """
    query_name = (nombre or "").strip()
    if not query_name:
        return {"success": False, "mensaje": "Indica el nombre del criterio a buscar"}

    active_only = _parse_bool(solo_activos, True)
    conditions = ["(sc.title ILIKE %s OR sc.prompt ILIKE %s)"]
    params: list[Any] = [f"%{query_name}%", f"%{query_name}%"]

    if active_only:
        conditions.append("sc.is_active = TRUE")

    campaign_filter: dict[str, Any] | None = None
    if campana and str(campana).strip():
        campaign, candidates = _resolve_campaign(campana=str(campana).strip())
        if not campaign:
            if candidates:
                return {
                    "success": False,
                    "mensaje": f"Hay varias campañas que coinciden con '{campana}'",
                    "candidatos": [
                        {"id": row.get("id"), "nombre": row.get("name")}
                        for row in candidates
                    ],
                }
            return {"success": False, "mensaje": f"No encontré la campaña '{campana}'"}
        campaign_filter = campaign
        conditions.append("sc.campaign_id = %s")
        params.append(int(campaign["id"]))

    where = " AND ".join(conditions)
    rows = fetch_all(
        f"""
        SELECT
            sc.id,
            sc.campaign_id,
            sc.title,
            sc.prompt,
            sc.weight,
            sc.is_active,
            sc.non_applicable_hint,
            sc.tipo,
            sc.categoria,
            sc.eval_kind,
            sc.is_important,
            sc.channels,
            camp.name AS campana_nombre
        FROM supervisor_criteria sc
        JOIN campaigns camp ON camp.id = sc.campaign_id
        WHERE {where}
        ORDER BY
            CASE
                WHEN LOWER(sc.title) = LOWER(%s) THEN 0
                WHEN sc.title ILIKE %s THEN 1
                ELSE 2
            END,
            sc.title ASC
        LIMIT 15
        """,
        tuple(params + [query_name, f"%{query_name}%"]),
    )

    if not rows and campaign_filter and campaign_filter.get("inherits_parent_criteria") is not False:
        effective = _fetch_effective_campaign_criteria(
            int(campaign_filter["id"]),
            active_only=active_only,
            include_inherited=True,
        )
        needle = query_name.lower()
        rows = [
            row
            for row in effective
            if needle in str(row.get("title", "")).lower()
            or needle in str(row.get("prompt", "")).lower()
        ]

    if not rows:
        suffix = f" en la campaña '{campana}'" if campana else ""
        return {
            "success": False,
            "mensaje": f"No encontré criterios que coincidan con '{query_name}'{suffix}",
        }

    criterios = [_serialize_criterion(row, include_prompt=True) for row in rows]
    if len(criterios) == 1:
        item = criterios[0]
        return {
            "success": True,
            "criterio": item,
            "criterios": criterios,
            "mensaje": (
                f"Criterio '{item.get('titulo')}' de la campaña "
                f"'{item.get('campana')}'"
            ),
        }

    return {
        "success": True,
        "total": len(criterios),
        "criterios": criterios,
        "mensaje": f"Encontré {len(criterios)} criterio(s) que coinciden con '{query_name}'",
    }


def listar_campanas_con_pocos_criterios(
    maximo: int | str | float = 10,
    solo_activas: bool | str = True,
    incluir_heredados: bool | str = True,
    limite: int | str | float = 50,
) -> dict[str, Any]:
    """
    Campañas con menos de N criterios de evaluación (propios + heredados si aplica).
  """
    try:
        maximo = int(float(maximo))
    except (ValueError, TypeError):
        maximo = 10
    maximo = max(1, min(maximo, 100))

    try:
        limite = int(float(limite))
    except (ValueError, TypeError):
        limite = 50
    limite = max(1, min(limite, 100))

    active_only = _parse_bool(solo_activas, True)
    include_inherited = _parse_bool(incluir_heredados, True)

    conditions: list[str] = []
    if active_only:
        conditions.append("is_active = TRUE")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    campaigns = fetch_all(
        f"""
        SELECT id, name, is_active, parent_id, inherits_parent_criteria
        FROM campaigns
        {where}
        ORDER BY name
        LIMIT %s
        """,
        (limite * 3,),
    )

    matches: list[dict[str, Any]] = []
    for camp in campaigns:
        criteria = _fetch_effective_campaign_criteria(
            int(camp["id"]),
            active_only=active_only,
            include_inherited=include_inherited,
        )
        total = len(criteria)
        if total < maximo:
            matches.append(
                {
                    "id": camp.get("id"),
                    "nombre": camp.get("name"),
                    "activa": camp.get("is_active"),
                    "total_criterios": total,
                }
            )
        if len(matches) >= limite:
            break

    matches.sort(key=lambda row: (row.get("total_criterios", 0), str(row.get("nombre", ""))))

    return {
        "success": True,
        "maximo_criterios": maximo,
        "incluye_heredados": include_inherited,
        "total": len(matches),
        "campanas": matches,
        "mensaje": (
            f"Encontré {len(matches)} campaña(s) con menos de {maximo} criterio(s)"
        ),
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
