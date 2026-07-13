from __future__ import annotations

import json
import re
from typing import Any

from services.user_constraints import (
    apply_transcript_constraints,
    combined_user_context,
    constraint_summary,
    extract_campaign_filter,
    extract_transcript_constraints,
    recent_user_texts,
)
from services.intent import extract_date_range
from tools.registry import execute_tool

CALL_ID = re.compile(
    r"(?:id|#|n[úu]mero)\s*[:#]?\s*(\d+)"
    r"|(?:llamada)\s+(\d+)\b"
    r"|(?:con\s+el\s+id)\s+(\d+)"
    r"|(?:el\s+id)\s+(\d+)"
    r"|(?:el\s+id\s+es)\s+(\d+)"
    r"|(?:id\s+es)\s+(\d+)"
    r"|(?:es|ser[ií]a)\s+(?:la\s+|el\s+)?(\d+)\b"
    r"|(?:llamada|id)[^.?!]{0,80}?(?:es|ser[ií]a)\s+(?:la\s+|el\s+)?(\d+)",
    re.IGNORECASE,
)

WEIGHTED_TOOL_HINTS: dict[str, list[tuple[str, int]]] = {
    "resumen_evaluacion_llamada": [
        (r"resumen\s+de\s+evaluaci", 6),
        (r"resumen\s+evaluaci", 6),
        (r"evaluaci[oó]n", 5),
        (r"compliance", 4),
        (r"\bscore\b", 3),
    ],
    "obtener_detalle_llamada": [
        (r"resumen\s+de\s+la\s+llamada", 9),
        (r"detalle\s+de\s+la\s+llamada", 9),
        (r"informaci[oó]n\s+de\s+la\s+llamada", 8),
        (r"calificaci[oó]n(?:es)?\s+(?:de\s+)?(?:la\s+)?llamada", 8),
        (r"criterios?\s+(?:de\s+)?(?:la\s+)?llamada", 8),
        (r"momentos?\s+clave", 7),
        (r"callgist|gesti[oó]n\s+callhistory", 7),
        (r"ac[uú]stic|estr[eé]s|silencio", 6),
        (r"auditor[ií]a", 5),
    ],
    "obtener_transcripcion_llamada": [
        (r"transcrip", 6),
        (r"transcri", 5),
        (r"di[aá]logo", 4),
        (r"texto de la llamada", 4),
    ],
    "buscar_llamadas": [
        (r"busca(?:r|)\s+(?:una?\s+)?llamad", 6),
        (r"busc(?:ar|a).{0,40}llamad", 5),
        (r"encuentr(?:ar|a).{0,40}llamad", 5),
        (r"listar?\s+llamad", 5),
        (r"llamadas?\s+(?:de|del|entre)", 5),
        (r"busca(?:r|a)", 4),
        (r"encuentr(?:ar|a)", 3),
        (r"consult(?:ar|a).{0,40}llamad", 4),
        (r"detalle.{0,20}llamad", 4),
        (r"info(?:rmaci[oó]n)?.{0,20}llamad", 4),
        (r"datos.{0,20}llamad", 4),
    ],
    "obtener_reporte_estadisticas": [
        (r"reporte.{0,30}estad", 7),
        (r"estad[ií]stica", 6),
        (r"m[eé]trica", 5),
        (r"promedio.{0,20}score", 5),
        (r"distribuci[oó]n.{0,20}sentimiento", 5),
        (r"reporte.{0,30}llamad", 5),
        (r"resumen.{0,30}llamad", 5),
    ],
}

CLARIFY_MESSAGES: dict[str, str] = {
    "buscar_llamadas": (
        "Claro, puedo buscar la llamada. Dime el **ID** (por ejemplo: `166`), "
        "o también puedo buscar por **cliente**, **campaña** o **fechas**."
    ),
    "resumen_evaluacion_llamada": (
        "Para darte el resumen de evaluación necesito el **ID de la llamada**. ¿Cuál es?"
    ),
    "obtener_transcripcion_llamada": (
        "Para mostrarte la transcripción necesito el **ID de la llamada**. ¿Cuál es?"
    ),
}

GENERAL_QUESTION_PATTERNS = (
    r"^(?:hola|buenos|buenas|hey|hi)\b",
    r"qu[eé]\s+es\s+(?:un\s+)?excel\b",
    r"qu[eé]\s+(?:m[aá]s\s+)?(?:puedes|pod[eé]s|haces|sabes|ofreces)",
    r"qu[eé]\s+(?:otras?\s+)?(?:herramientas?|funciones?|cosas?|opciones?)",
    r"(?:lista|enumera|dime|mu[eé]strame)\s+(?:las?\s+)?(?:herramientas?|funciones?|capacidades?|opciones?)",
    r"c[oó]mo\s+(?:funciona|te\s+uso|puedo\s+usarte)",
    r"(?:en\s+qu[eé]|qu[eé]\s+m[aá]s)\s+(?:me\s+)?(?:puedes|pod[eé]s)\s+(?:ayudar|hacer)",
    r"^\s*(?:gracias|ok|vale|perfecto|entendido|okey)\s*[,!.]?$",
    r"^\s*okey,?\s+qu[eé]\s+es\b",
)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    texts = recent_user_texts(messages, limit=1)
    return texts[0] if texts else ""


def _conversation_context(messages: list[dict[str, Any]], limit: int = 10) -> str:
    parts: list[str] = []
    for message in messages[-limit:]:
        role = str(message.get("role", "")).lower()
        if role not in ("user", "assistant"):
            continue
        content = str(message.get("content", "")).strip()
        if content:
            parts.append(content)
    return "\n".join(parts)


def _extract_call_id(text: str) -> int | None:
    match = CALL_ID.search(text)
    if match:
        for group in match.groups():
            if group:
                return int(group)
    simple = re.search(r"\bid\s+(\d+)\b", text, re.IGNORECASE)
    if simple:
        return int(simple.group(1))
    lone = re.fullmatch(r"\s*(\d{1,10})\s*", text.strip())
    if lone:
        return int(lone.group(1))
    return None


def _extract_call_id_from_context(messages: list[dict[str, Any]]) -> int | None:
    for text in reversed(recent_user_texts(messages, limit=6)):
        call_id = _extract_call_id(text)
        if call_id is not None:
            return call_id
    return None


def _score_tool_in_context(context: str, tool: str) -> int:
    score = 0
    for pattern, weight in WEIGHTED_TOOL_HINTS.get(tool, []):
        if re.search(pattern, context, re.IGNORECASE):
            score += weight
    return score


def _current_tool_scores(text: str, allowed: set[str]) -> dict[str, int]:
    return {
        tool: _score_tool_in_context(text, tool)
        for tool in WEIGHTED_TOOL_HINTS
        if tool in allowed
    }


def _infer_tool_from_context(context: str, allowed: set[str]) -> str | None:
    scores = {
        tool: _score_tool_in_context(context, tool)
        for tool in WEIGHTED_TOOL_HINTS
        if tool in allowed
    }
    if not scores:
        return None
    best_tool, best_score = max(scores.items(), key=lambda item: item[1])
    return best_tool if best_score > 0 else None


def _is_general_question(text: str) -> bool:
    lowered = text.lower().strip()
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in GENERAL_QUESTION_PATTERNS)


def _normalize_tool_hint(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    return re.sub(r"\s+", "_", lowered).strip("_")


def _detect_explicit_tool_request(text: str, allowed: set[str]) -> dict[str, Any] | None:
    """'Usa la función de resumen estadísticas' → ejecuta la tool por nombre."""
    match = re.search(
        r"usa(?:r)?\s+(?:la\s+)?(?:funci[oó]n|herramienta|tool)\s+(?:de\s+)?([^\n,.?!]+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None

    hint = _normalize_tool_hint(match.group(1))
    if not hint:
        return None

    aliases = {
        "crm_resumen_estadisticas": (
            "resumen_estadisticas",
            "resumen_estadistica",
            "estadisticas",
            "estadistica",
        ),
        "crm_dashboard_resumen": ("dashboard", "dashboard_resumen", "dashboard_crm"),
    }

    for tool in allowed:
        tool_slug = tool.lower()
        if hint == tool_slug or hint in tool_slug or tool_slug in hint:
            return {"tool": tool, "args": {}, "user_text": text}
        for alias in aliases.get(tool, ()):
            if alias in hint or hint in alias:
                return {"tool": tool, "args": {}, "user_text": text}

    return None


def _detect_crm_stats_intent(
    text: str,
    user_context: str,
    allowed: set[str],
) -> dict[str, Any] | None:
    """Resumen/estadísticas CRM — solo mensajes del usuario (no contamina el listado de tools del asistente)."""
    wants_stats_now = re.search(
        r"estad[ií]stica|resumen\s+(?:de\s+)?(?:las?\s+)?estad|m[eé]trica(?:s)?(?:\s+del?\s+crm)?|dashboard",
        text,
        re.IGNORECASE,
    )
    followup_period = re.search(
        r"(?:las?|los?)\s+(?:del?\s+)?(?:de\s+)?(?:este\s+mes|el\s+mes|esta\s+semana|hoy)"
        r"|(?:del?\s+)?(?:este\s+mes|esta\s+semana)\b",
        text,
        re.IGNORECASE,
    )
    prior_user = user_context.rsplit("\n", 1)[0] if user_context else ""
    wants_stats_prior = bool(
        prior_user
        and re.search(
            r"estad[ií]stica|resumen\s+(?:de\s+)?(?:las?\s+)?estad|m[eé]trica(?:s)?|dashboard",
            prior_user,
            re.IGNORECASE,
        )
    )

    if not wants_stats_now and not (followup_period and wants_stats_prior):
        return None

    date_source = f"{user_context}\n{text}".strip()
    date_range = extract_date_range(date_source)
    if "crm_dashboard_resumen" in allowed and date_range:
        return {
            "tool": "crm_dashboard_resumen",
            "args": {"fecha_inicio": date_range[0], "fecha_fin": date_range[1]},
            "user_text": text,
        }

    if "crm_resumen_estadisticas" in allowed and wants_stats_now:
        return {"tool": "crm_resumen_estadisticas", "args": {}, "user_text": text}

    return None


def _is_id_followup(text: str) -> bool:
    lowered = text.strip().lower()
    if re.fullmatch(r"\d{1,10}", lowered):
        return True
    return bool(
        re.search(
            r"(?:^|\b)(?:el\s+)?id\s+(?:es\s+)?\d+"
            r"|(?:^|\b)(?:es|ser[ií]a)\s+(?:la\s+|el\s+)?\d+"
            r"|(?:id|llamada).{0,80}?(?:es|ser[ií]a)\s+(?:la\s+|el\s+)?\d+",
            lowered,
            re.IGNORECASE,
        )
    )


def _resolve_call_id(
    text: str,
    messages: list[dict[str, Any]],
    current_scores: dict[str, int],
) -> int | None:
    call_id = _extract_call_id(text)
    if call_id is not None:
        return call_id

    if _is_id_followup(text):
        return _extract_call_id_from_context(messages)

    if max(current_scores.values(), default=0) >= 4:
        return _extract_call_id_from_context(messages)

    return None


def _pick_best_tool(current_scores: dict[str, int], full_context: str, allowed: set[str]) -> str:
    if max(current_scores.values(), default=0) > 0:
        return max(current_scores, key=current_scores.get)  # type: ignore[arg-type]
    inferred = _infer_tool_from_context(full_context, allowed)
    return inferred or "buscar_llamadas"


def _detect_clarification(
    text: str,
    allowed: set[str],
    call_id: int | None,
) -> dict[str, Any] | None:
    if call_id is not None:
        return None

    lowered = text.lower()
    current_scores = _current_tool_scores(text, allowed)

    for tool, score in current_scores.items():
        if score >= 4 and tool in CLARIFY_MESSAGES:
            return {
                "type": "clarify",
                "pending_tool": tool,
                "message": CLARIFY_MESSAGES[tool],
            }

    return None


def _infer_call_detail_section(text: str) -> str:
    lowered = text.lower()
    if re.search(r"transcrip", lowered):
        return "transcripcion"
    if re.search(r"whatsapp|chat\b", lowered):
        return "chat"
    if re.search(r"criterio|calificaci", lowered):
        return "criterios"
    if re.search(r"ac[uú]stic|estr[eé]s|silencio|pitch", lowered):
        return "acustica"
    if re.search(r"callgist|callhistory", lowered):
        return "callgist"
    if re.search(r"resumen|detalle|informaci", lowered):
        return "resumen"
    return "completo"


def _format_call_detail_body(data: dict[str, Any]) -> str:
    detalle = data.get("detalle") or {}
    cab = detalle.get("cabecera") or {}
    score = detalle.get("score") or {}
    resumen = detalle.get("resumen") or {}
    criterios = detalle.get("criterios") or {}
    acustica = detalle.get("acustica")
    transcripcion = detalle.get("transcripcion") or {}
    chat = detalle.get("chat_whatsapp") or {}
    callgist = detalle.get("callgist")

    lines = [
        f"**Auditoría Qontrol — llamada #{data.get('call_id')}**",
        f"- Cliente: **{cab.get('cliente', 'N/D')}**"
        + (f" (CC {cab.get('documento_cliente')})" if cab.get("documento_cliente") else ""),
        f"- Agente: {cab.get('agente', 'N/D')}"
        + (f" (CC {cab.get('documento_agente')})" if cab.get("documento_agente") else ""),
        f"- Campaña: {cab.get('campana', 'N/D')} · Canal: {cab.get('canal', 'N/D')}",
        f"- Marcada: {'Sí' if cab.get('marcada') else 'No'}",
        f"- Fecha llamada: {cab.get('fecha_llamada') or 'N/D'} · Auditoría: {cab.get('fecha_auditoria', 'N/D')}",
    ]

    if score:
        lines.extend([
            "",
            f"**{score.get('etiqueta', 'Score')}:** {score.get('valor', 'N/D')}%"
            + (f" · Sentimiento: **{score.get('sentimiento')}**" if score.get("sentimiento") else ""),
        ])
        if score.get("calibrado"):
            lines.append("_Calibración humana aplicada._")

    if resumen.get("texto"):
        lines.extend(["", "**Resumen IA**", resumen["texto"]])

    momentos = resumen.get("momentos_clave") or []
    if momentos:
        lines.append("\n**Momentos clave**")
        for idx, momento in enumerate(momentos[:8], start=1):
            texto = momento.get("text") if isinstance(momento, dict) else str(momento)
            start = momento.get("start") if isinstance(momento, dict) else None
            suffix = f" (t+{int(start)}s)" if isinstance(start, (int, float)) and start > 0 else ""
            lines.append(f"{idx}. {texto}{suffix}")

    if callgist:
        lines.extend([
            "",
            f"**CallHistory — {'Alineada' if callgist.get('aligned') else 'Con diferencias'}**",
            callgist.get("comparisonSummary") or callgist.get("comparison_summary") or "",
        ])
        if callgist.get("managementText") or callgist.get("management_text"):
            lines.append(f"_CRM:_ {callgist.get('managementText') or callgist.get('management_text')}")

    if criterios.get("resultados"):
        lines.extend([
            "",
            f"**Criterios** — {criterios.get('cumplidos', 0)} cumplidos / "
            f"{criterios.get('no_cumplidos', 0)} no cumplidos "
            f"(evaluados {criterios.get('total_evaluados', 0)})",
        ])
        for item in criterios.get("resultados", [])[:12]:
            lines.append(
                f"- **{item.get('titulo', 'Criterio')}** · {item.get('estado', 'N/D')}"
                + (f" · peso {item.get('peso')}%" if item.get("peso") is not None else "")
            )
            if item.get("justificacion"):
                lines.append(f"  _{str(item['justificacion'])[:220]}_")

    if acustica:
        lines.extend([
            "",
            "**Análisis acústico**",
            f"- Pitch promedio: {acustica.get('average_pitch', 'N/D')} Hz",
            f"- Pico energía: {acustica.get('peak_energy', 'N/D')}",
            f"- Silencios >3s: {acustica.get('silence_count', 'N/D')}",
            f"- Estrés detectado: {'Sí' if acustica.get('stress_detected') else 'No'}",
        ])

    segmentos = transcripcion.get("segmentos") or []
    if segmentos:
        lines.extend(["", f"**Transcripción** ({transcripcion.get('total_segmentos', len(segmentos))} segmentos)"])
        for seg in segmentos[:15]:
            speaker = seg.get("speaker", "N/D")
            text = seg.get("text", "")
            lines.append(f"- **{speaker}:** {text[:240]}")

    mensajes = chat.get("mensajes") or []
    if mensajes:
        lines.extend(["", f"**Chat WhatsApp** ({chat.get('total_mensajes', len(mensajes))} mensajes)"])
        for msg in mensajes[:12]:
            if isinstance(msg, dict):
                sender = msg.get("sender") or msg.get("senderName") or "N/D"
                content = msg.get("content") or msg.get("text") or ""
                lines.append(f"- **{sender}:** {str(content)[:200]}")

    return "\n".join(lines)


def _format_tool_result(
    tool: str,
    raw: str,
    *,
    user_text: str = "",
    context_text: str = "",
) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if not data.get("success", True) and data.get("error"):
        return f"No pude completar la consulta: {data['error']}"
    if data.get("success") is False:
        return data.get("mensaje") or "No encontré resultados."

    summary = constraint_summary(context_text or user_text, tool=tool)
    prefix = f"{summary}\n\n" if summary else ""

    if tool == "obtener_transcripcion_llamada":
        call = data.get("llamada") or {}
        constraints = extract_transcript_constraints(context_text or user_text)
        transcript, notes = apply_transcript_constraints(data.get("transcripcion"), constraints)
        if not transcript:
            return (
                f"Encontré la llamada **#{data.get('call_id')}** "
                f"({call.get('customer_name', 'sin cliente')}) pero **no tiene transcripción** guardada."
            )
        header = (
            f"**Transcripción — llamada #{data.get('call_id')}**\n"
            f"Cliente: {call.get('customer_name', 'N/D')}\n"
            f"Fecha: {call.get('created_at', 'N/D')}\n"
        )
        if notes:
            header += "\n".join(f"_{note}_" for note in notes) + "\n"
        header += "\n---\n\n"
        return prefix + header + transcript

    if tool == "resumen_evaluacion_llamada":
        return prefix + (
            f"**Evaluación — llamada #{data.get('call_id')}**\n"
            f"Cliente: {data.get('cliente', 'N/D')}\n"
            f"Compliance score: {data.get('compliance_score', 'N/D')}\n\n"
            f"{data.get('ai_evaluation') or json.dumps(data.get('evaluation_data'), ensure_ascii=False, indent=2)}"
        )

    if tool == "obtener_detalle_llamada":
        if not data.get("success"):
            return prefix + (data.get("mensaje") or "No encontré el detalle de esa llamada.")
        return prefix + _format_call_detail_body(data)

    if tool == "listar_campanas":
        campaigns = data.get("campanas") or []
        if not campaigns:
            filtro = data.get("filtro_nombre")
            if filtro:
                return prefix + f"No encontré campañas que coincidan con **{filtro}**."
            return prefix + (data.get("mensaje") or "Sin campañas.")

        lines = [f"**{data.get('mensaje', 'Campañas')}**\n"]
        for camp in campaigns:
            estado = "activa" if camp.get("is_active") else "inactiva"
            lines.append(f"- **{camp.get('name')}** ({estado}) — id {camp.get('id')}")
        return prefix + "\n".join(lines)

    if tool == "listar_escalaciones":
        lines = [f"**{data.get('mensaje', 'Escalaciones')}**\n"]
        for row in data.get("escalaciones") or []:
            lines.append(
                f"- #{row.get('id')} · {row.get('status')} · nivel {row.get('level')} · {row.get('reason', '')[:80]}"
            )
        return prefix + ("\n".join(lines) if len(lines) > 1 else data.get("mensaje", "Sin escalaciones."))

    if tool == "buscar_llamadas":
        calls = data.get("llamadas") or []
        if data.get("call_id") and len(calls) == 1:
            row = calls[0]
            return prefix + (
                f"**Llamada #{row.get('id')}**\n"
                f"Cliente: {row.get('customer_name', 'N/D')}\n"
                f"Campaña: {row.get('campana_nombre') or row.get('campana') or 'N/D'}\n"
                f"Canal: {row.get('channel', 'N/D')}\n"
                f"Agente: {row.get('agente', 'N/D')}\n"
                f"Marcada: {'Sí' if row.get('is_flagged') else 'No'}\n"
                f"Fecha: {row.get('created_at', 'N/D')}"
            )

        if not calls:
            return prefix + (
                f"No encontré llamadas entre **{data.get('fecha_inicio')}** y **{data.get('fecha_fin')}**.\n\n"
                "Amplía el rango de fechas o confirma que la base SalesCloser tenga datos en ese periodo."
            )

        lines = [
            f"**{data.get('mensaje')}** ({data.get('fecha_inicio')} → {data.get('fecha_fin')})\n"
        ]
        for row in calls:
            lines.append(
                f"- #{row.get('id')} · {row.get('customer_name')} · {row.get('campana_nombre') or row.get('campana')} · {row.get('created_at')}"
            )
        return prefix + "\n".join(lines)

    if tool == "crm_buscar_clientes":
        if not data.get("success"):
            return prefix + f"No pude consultar el CRM: {data.get('error', 'error desconocido')}"
        clientes = data.get("clientes") or []
        if not clientes:
            return prefix + (data.get("mensaje") or "No encontré clientes con esos criterios.")
        lines = [f"**{data.get('mensaje', 'Clientes encontrados')}**\n"]
        for row in clientes[:20]:
            lines.append(
                f"- **{row.get('full_name') or row.get('name', 'N/D')}** · doc "
                f"{row.get('document_number') or row.get('document_id', 'N/D')} · "
                f"{row.get('city', 'N/D')} · {row.get('client_status') or row.get('status', 'N/D')}"
            )
        if data.get("total", len(clientes)) > len(clientes):
            lines.append(f"\n_Mostrando {len(clientes)} de {data.get('total')}._")
        return prefix + "\n".join(lines)

    if tool == "crm_buscar_usuarios":
        usuarios = data.get("usuarios") or []
        if not usuarios:
            return prefix + (data.get("mensaje") or "No encontré usuarios con esos criterios.")
        lines = [f"**{data.get('mensaje', 'Usuarios encontrados')}**\n"]
        for row in usuarios[:20]:
            lines.append(
                f"- **{row.get('full_name') or row.get('username', 'N/D')}** · "
                f"{row.get('email', 'N/D')} · rol {row.get('role', 'N/D')}"
            )
        return prefix + "\n".join(lines)

    if tool in ("crm_listar_gestiones", "crm_obtener_gestion"):
        gestiones = data.get("gestiones") or ([data.get("gestion")] if data.get("gestion") else [])
        if not gestiones:
            return prefix + (data.get("mensaje") or "No encontré gestiones con esos criterios.")
        lines = [f"**{data.get('mensaje', 'Gestiones')}**\n"]
        for row in gestiones[:15]:
            alias = row.get("gestion_alias") or str(row.get("id", ""))[:8]
            lines.append(
                f"- **{alias}** · {row.get('customer_name', 'N/D')} "
                f"({row.get('document_number', 'sin doc')}) · "
                f"{row.get('action_name') or 'sin acción'} → {row.get('result_name') or 'sin resultado'} · "
                f"{row.get('created_at', 'N/D')}"
            )
            if row.get("text_management"):
                snippet = str(row["text_management"])[:120]
                lines.append(f"  _{snippet}{'…' if len(str(row['text_management'])) > 120 else ''}_")
        if data.get("total", len(gestiones)) > len(gestiones):
            lines.append(f"\n_Mostrando {len(gestiones)} de {data.get('total')}._")
        return prefix + "\n".join(lines)

    if tool == "crm_resumen_estadisticas":
        stats = data.get("estadisticas") or {}
        clientes = stats.get("clientes") or {}
        usuarios = stats.get("usuarios") or {}
        chats = stats.get("whatsapp_chats") or {}
        return prefix + (
            f"**Resumen CRM**\n"
            f"Clientes totales: {clientes.get('total', 'N/D')}\n"
            f"Usuarios activos: {usuarios.get('activos', 'N/D')} / {usuarios.get('total', 'N/D')}\n"
            f"Chats WhatsApp: {chats.get('total', 'N/D')}\n"
            f"{data.get('mensaje', '')}"
        )

    if tool == "crm_listar_arboles_tipificacion":
        arboles = data.get("arboles") or []
        if not arboles:
            return prefix + (data.get("mensaje") or "No hay árboles de tipificación.")
        lines = [f"**{data.get('mensaje')}**\n"]
        for row in arboles:
            estado = "activo" if row.get("is_active") else "inactivo"
            lines.append(f"- **{row.get('name')}** ({estado}) — id `{row.get('id')}`")
        return prefix + "\n".join(lines)

    if tool == "crm_arbol_capas":
        capas = data.get("capas") or []
        arbol = data.get("arbol") or {}
        lines = [f"**Capas — {arbol.get('name', 'árbol')}**\n"]
        for row in capas:
            lines.append(
                f"- Nivel {row.get('level')}: **{row.get('name')}** "
                f"({row.get('items_count', 0)} ítems) — id `{row.get('id')}`"
            )
        return prefix + ("\n".join(lines) if len(lines) > 1 else data.get("mensaje", "Sin capas."))

    if tool == "crm_listar_flujos":
        flujos = data.get("flujos") or []
        if not flujos:
            return prefix + (data.get("mensaje") or "No hay flujos en ese árbol.")
        lines = [f"**{data.get('mensaje')}**\n"]
        for row in flujos:
            pasos = row.get("pasos") or []
            paso_txt = " → ".join(p.get("name", "?") for p in pasos[:6]) if pasos else "sin pasos resueltos"
            lines.append(f"- **{row.get('name')}** — {paso_txt}")
        return prefix + "\n".join(lines)

    if tool == "crm_buscar_items_capa":
        items = data.get("items") or []
        capa = data.get("capa") or {}
        if not items:
            return prefix + f"No encontré ítems en la capa **{capa.get('name', 'N/D')}**."
        lines = [f"**Ítems — {capa.get('name')} (árbol {capa.get('arbol', 'N/D')})**\n"]
        for row in items:
            lines.append(f"- `{row.get('code')}` **{row.get('name')}** — id `{row.get('id')}`")
        return prefix + "\n".join(lines)

    if tool == "crm_dashboard_resumen":
        metricas = data.get("metricas") or {}
        periodo = data.get("periodo") or {}
        lines = [
            f"**Dashboard CRM** ({periodo.get('fecha_inicio')} → {periodo.get('fecha_fin')})\n",
            f"- Gestiones en periodo: **{metricas.get('gestiones_periodo', 0)}**",
            f"- Clientes nuevos: **{metricas.get('clientes_nuevos_periodo', 0)}**",
            f"- Agentes online: **{metricas.get('agentes_online', 0)}**",
            f"- Chats WhatsApp activos: **{metricas.get('chats_whatsapp_activos', 0)}**",
        ]
        por_canal = metricas.get("gestiones_por_canal") or []
        if por_canal:
            lines.append("\n**Gestiones por canal:**")
            for row in por_canal[:8]:
                lines.append(f"- {row.get('canal') or 'Sin canal'}: {row.get('total')}")
        return prefix + "\n".join(lines)

    if tool == "crm_dashboard_whatsapp":
        metricas = data.get("metricas") or {}
        periodo = data.get("periodo") or {}
        lines = [
            f"**Dashboard WhatsApp** ({periodo.get('fecha_inicio')} → {periodo.get('fecha_fin')})\n",
            f"- Chats con actividad: **{metricas.get('chats_con_actividad_periodo', 0)}**",
            f"- Mensajes en periodo: **{metricas.get('mensajes_periodo', 0)}**",
            f"- Chats activos ahora: **{metricas.get('chats_activos_ahora', 0)}**",
        ]
        for row in metricas.get("distribucion_estado") or []:
            lines.append(f"- {row.get('estado')}: {row.get('total')}")
        return prefix + "\n".join(lines)

    if tool == "crm_dashboard_tipologico":
        periodo = data.get("periodo") or {}
        lines = [
            f"**Tipológico CRM** ({periodo.get('fecha_inicio')} → {periodo.get('fecha_fin')})\n",
            f"Total gestiones: **{data.get('total_gestiones', 0)}**\n",
            "\n**Por canal:**",
        ]
        for row in (data.get("por_canal") or [])[:8]:
            lines.append(f"- {row.get('etiqueta')}: {row.get('total')}")
        lines.append("\n**Por acción:**")
        for row in (data.get("por_accion") or [])[:8]:
            lines.append(f"- {row.get('etiqueta')}: {row.get('total')}")
        lines.append("\n**Top combinaciones:**")
        for row in (data.get("combinaciones_top") or [])[:6]:
            lines.append(
                f"- {row.get('canal')} → {row.get('accion')} → {row.get('resultado')}: {row.get('total')}"
            )
        return prefix + "\n".join(lines)

    if tool == "crm_reporte_estados_agentes":
        periodo = data.get("periodo") or {}
        lines = [
            f"**Estados de agentes** ({periodo.get('fecha_inicio')} → {periodo.get('fecha_fin')})\n",
        ]
        for row in data.get("resumen_por_estado") or []:
            lines.append(f"- {row.get('estado')}: {row.get('total')}")
        lines.append("\n**Últimos cambios:**")
        for row in (data.get("ultimos_cambios") or [])[:10]:
            lines.append(
                f"- {row.get('agente')} · {row.get('from_status')} → {row.get('to_status')} · {row.get('changed_at')}"
            )
        return prefix + "\n".join(lines)

    if tool == "crm_listar_conexiones":
        conexiones = data.get("conexiones") or []
        lines = [f"**{data.get('mensaje', 'Conexiones')}**\n"]
        for row in conexiones:
            lines.append(
                f"- `{row.get('connection_id')}` · dept `{row.get('department_id')}` · "
                f"bot {row.get('bot_name') or 'N/D'} · IA {'sí' if row.get('ai_enabled') else 'no'}"
            )
        return prefix + "\n".join(lines)

    if tool == "obtener_reporte_estadisticas":
        stats = data.get("estadisticas") or {}
        filtros = data.get("filtros") or {}
        total = stats.get("total_llamadas", 0)
        if total == 0:
            campana_txt = f" para campaña «{filtros.get('campana')}»" if filtros.get("campana") else ""
            agente_txt = f" ni agente «{filtros.get('agente')}»" if filtros.get("agente") else ""
            return prefix + (
                f"No hay llamadas en el periodo **{filtros.get('fecha_inicio')} → {filtros.get('fecha_fin')}**"
                f"{campana_txt}{agente_txt}.\n\n"
                "Prueba ampliar el rango de fechas (ej. últimos 30 días) o quitar filtros."
            )
        lines = [
            f"**Reporte de llamadas** ({filtros.get('fecha_inicio')} → {filtros.get('fecha_fin')})\n",
            f"- Total: **{total}**",
            f"- Score promedio: **{stats.get('score_promedio_efectivo', 'N/D')}**",
            f"- Marcadas: **{stats.get('llamadas_marcadas', 0)}** ({stats.get('tasa_marcadas_porcentaje', 0)}%)",
        ]
        sentiment = stats.get("distribucion_sentimiento") or {}
        if sentiment:
            lines.append("- Sentimiento: " + ", ".join(f"{k}: {v}" for k, v in sentiment.items()))
        detalles = data.get("detalles_llamadas") or []
        if detalles:
            lines.append("\n**Últimas llamadas:**")
            for row in detalles[:10]:
                lines.append(
                    f"- #{row.get('id')} · {row.get('customer_name')} · "
                    f"score {row.get('effective_score', 'N/D')} · {row.get('created_at')}"
                )
        return prefix + "\n".join(lines)

    if tool == "generar_poster_alerta":
        if not data.get("success"):
            return prefix + (data.get("mensaje") or "No pude generar el poster.")
        return prefix + (
            f"**Poster generado** ({data.get('tema', 'alerta')})\n\n"
            f"![Poster]({data.get('url')})\n\n"
            f"[Descargar SVG]({data.get('url')})"
        )

    if tool == "ejecutar_consulta_crm":
        if not data.get("success"):
            return prefix + f"No pude ejecutar la consulta: {data.get('error', 'error desconocido')}"
        rows = data.get("resultados") or []
        lines = [f"**{data.get('mensaje', 'Consulta CRM')}**\n"]
        for row in rows[:15]:
            lines.append(f"- {json.dumps(row, ensure_ascii=False)}")
        return prefix + "\n".join(lines)

    return prefix + (data.get("mensaje") or json.dumps(data, ensure_ascii=False, indent=2))


def _extract_documento(text: str) -> str | None:
    match = re.search(r"\b(\d{6,15})\b", text)
    return match.group(1) if match else None


def _extract_gestion_id(text: str) -> str | None:
    uuid_match = re.search(
        r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
        text,
        re.IGNORECASE,
    )
    if uuid_match:
        return uuid_match.group(1)
    alias_match = re.search(r"\b(?:gesti[oó]n|alias)\s+([A-Z0-9]{4,12})\b", text, re.IGNORECASE)
    if alias_match:
        return alias_match.group(1)
    return None


def _wants_ultima_gestion(text: str) -> bool:
    """Una sola gestión: 'última gestión'."""
    return bool(re.search(r"[uú]ltim[ao]\s+gesti[oó]n\b", text, re.IGNORECASE))


def _wants_gestiones_recientes(text: str) -> bool:
    """Varias gestiones: 'últimas gestiones', 'gestiones recientes'."""
    return bool(
        re.search(
            r"[uú]ltimas?\s+gesti[oó]nes?|gesti[oó]n(?:es)?\s+recientes?",
            text,
            re.IGNORECASE,
        )
    )


def _extract_poster_fields(text: str) -> dict[str, str]:
    titulo = None
    mensaje = None
    for pattern in (
        r"t[ií]tulo\s+[\"']([^\"']+)[\"']",
        r"t[ií]tulo\s+([^,\n]+)",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            titulo = match.group(1).strip().strip("'\"")
            break
    for pattern in (
        r"mensaje\s+[\"']([^\"']+)[\"']",
        r"mensaje\s+(.+)$",
    ):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            mensaje = match.group(1).strip().strip("'\"")
            break
    return {
        "titulo": titulo or "Aviso importante",
        "mensaje": mensaje or text[:240],
    }


def _tool_result_files(raw: str) -> list[str] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not data.get("success", True):
        return None
    url = data.get("url")
    if url:
        return [str(url)]
    return None


def detect_sync_tool_intent(
    messages: list[dict[str, Any]],
    available_tools: list[str] | None,
) -> dict[str, Any] | None:
    if not available_tools:
        return None

    allowed = set(available_tools)
    text = _last_user_text(messages)
    user_context = combined_user_context(messages)
    full_context = _conversation_context(messages)

    if _is_general_question(text):
        return None

    explicit = _detect_explicit_tool_request(text, allowed)
    if explicit:
        tool = explicit["tool"]
        args = dict(explicit.get("args") or {})
        if tool == "crm_dashboard_resumen" or tool == "crm_resumen_estadisticas":
            date_range = extract_date_range(f"{user_context}\n{text}".strip())
            if date_range and "crm_dashboard_resumen" in allowed:
                return {
                    "tool": "crm_dashboard_resumen",
                    "args": {"fecha_inicio": date_range[0], "fecha_fin": date_range[1]},
                    "user_text": text,
                }
        return explicit

    doc_match = _extract_documento(text)
    if "crm_buscar_clientes" in allowed and re.search(
        r"busca(?:r|a).{0,40}cliente|cliente.{0,40}\d|documento|c[eé]dula",
        text,
        re.IGNORECASE,
    ):
        args: dict[str, Any] = {}
        if doc_match:
            args["documento"] = doc_match
        else:
            name = re.search(r"cliente\s+([^\n,.?!]+)", text, re.IGNORECASE)
            if name:
                args["query"] = name.group(1).strip()
        if args:
            return {"tool": "crm_buscar_clientes", "args": args, "user_text": text}

    stats_intent = _detect_crm_stats_intent(text, user_context, allowed)
    if stats_intent:
        return stats_intent

    if "generar_poster_alerta" in allowed and re.search(
        r"(?:crea|genera|haz).{0,24}(?:poster|cartel)|\bposter\b|\bcartel\b|aviso\s+visual",
        text,
        re.IGNORECASE,
    ):
        fields = _extract_poster_fields(text)
        poster_args: dict[str, Any] = {
            "titulo": fields["titulo"],
            "mensaje": fields["mensaje"],
            "tema": "info",
        }
        if re.search(r"alerta|urgent|mantenimiento", text, re.IGNORECASE):
            poster_args["tema"] = "alerta"
        elif re.search(r"[eé]xito|confirm", text, re.IGNORECASE):
            poster_args["tema"] = "exito"
        elif re.search(r"aviso", text, re.IGNORECASE):
            poster_args["tema"] = "aviso"
        return {"tool": "generar_poster_alerta", "args": poster_args, "user_text": text}

    current_scores = _current_tool_scores(text, allowed)
    call_id = _resolve_call_id(text, messages, current_scores)

    if "obtener_detalle_llamada" in allowed:
        detail_call_id = call_id or _extract_call_id(text) or _extract_call_id_from_context(messages)
        if detail_call_id and re.search(
            r"resumen|detalle|informaci|calificaci|criterio|auditor[ií]a|llamada|ac[uú]stic|callgist|momentos?",
            text,
            re.IGNORECASE,
        ):
            return {
                "tool": "obtener_detalle_llamada",
                "args": {
                    "call_id": detail_call_id,
                    "seccion": _infer_call_detail_section(text),
                },
                "user_text": text,
            }

    clarify = _detect_clarification(text, allowed, call_id)
    if clarify:
        return clarify

    if call_id is not None:
        has_current_intent = max(current_scores.values(), default=0) >= 4
        if not has_current_intent and not _is_id_followup(text):
            return None

        best_tool = _pick_best_tool(current_scores, full_context, allowed)

        if (
            "obtener_detalle_llamada" in allowed
            and best_tool == "obtener_detalle_llamada"
        ):
            return {
                "tool": "obtener_detalle_llamada",
                "args": {
                    "call_id": call_id,
                    "seccion": _infer_call_detail_section(text),
                },
                "user_text": text,
            }

        if (
            "obtener_transcripcion_llamada" in allowed
            and best_tool == "obtener_transcripcion_llamada"
        ):
            return {
                "tool": "obtener_transcripcion_llamada",
                "args": {"call_id": call_id},
                "user_text": text,
            }

        if (
            "resumen_evaluacion_llamada" in allowed
            and best_tool == "resumen_evaluacion_llamada"
        ):
            return {
                "tool": "resumen_evaluacion_llamada",
                "args": {"call_id": call_id},
                "user_text": text,
            }

        if "buscar_llamadas" in allowed and (
            best_tool == "buscar_llamadas" or has_current_intent or _is_id_followup(text)
        ):
            return {
                "tool": "buscar_llamadas",
                "args": {"call_id": call_id},
                "user_text": text,
            }

    if "listar_campanas" in allowed and re.search(
        r"listar?\s+campa|listame|campan[as]|campañas",
        text.lower(),
    ):
        solo = "todas" not in text.lower()
        args: dict[str, Any] = {"solo_activas": solo}
        campaign_name, exact = extract_campaign_filter(user_context)
        if campaign_name:
            args["nombre"] = campaign_name
            args["nombre_exacto"] = exact
        return {"tool": "listar_campanas", "args": args, "user_text": text}

    if "listar_escalaciones" in allowed and "escalaci" in text.lower():
        estado = "PENDING"
        if "resuelt" in text.lower():
            estado = "RESOLVED"
        return {"tool": "listar_escalaciones", "args": {"estado": estado}, "user_text": text}

    doc_match = _extract_documento(text)

    # crm_buscar_clientes: bloque duplicado al final por compatibilidad (el early-return ya cubre la mayoría)
    gestion_id = _extract_gestion_id(text)
    if "crm_obtener_gestion" in allowed and gestion_id and re.search(
        r"gesti[oó]n|gestiones",
        text,
        re.IGNORECASE,
    ):
        return {"tool": "crm_obtener_gestion", "args": {"gestion_id": gestion_id}, "user_text": text}

    if "crm_listar_gestiones" in allowed and re.search(
        r"gesti[oó]n|gestiones|tipific",
        text,
        re.IGNORECASE,
    ):
        args: dict[str, Any] = {}
        if doc_match:
            args["documento"] = doc_match
        if _wants_ultima_gestion(text):
            args["solo_ultima"] = True
        elif _wants_gestiones_recientes(text):
            args["limite"] = args.get("limite", 15)
        else:
            cliente = re.search(r"cliente\s+([^\n,.?!]+)", text, re.IGNORECASE)
            if cliente:
                args["cliente"] = cliente.group(1).strip()
            asesor = re.search(r"(?:asesor|agente)\s+([^\n,.?!]+)", text, re.IGNORECASE)
            if asesor:
                args["asesor"] = asesor.group(1).strip()
            date_range = extract_date_range(full_context)
            if date_range:
                args["fecha_inicio"], args["fecha_fin"] = date_range
            limite_match = re.search(r"(?:limite|l[ií]mite|top)\s+(\d+)", text, re.IGNORECASE)
            if limite_match:
                args["limite"] = int(limite_match.group(1))
        if gestion_id:
            args["gestion_id"] = gestion_id
        if args or re.search(r"listar?\s+gesti|gestiones", text, re.IGNORECASE):
            return {"tool": "crm_listar_gestiones", "args": args, "user_text": text}

    if "crm_dashboard_resumen" in allowed and re.search(
        r"dashboard|m[eé]trica|resumen.{0,20}crm",
        text,
        re.IGNORECASE,
    ) and not re.search(r"whatsapp|tipol[oó]g|agente", text, re.IGNORECASE):
        args = {}
        date_range = extract_date_range(f"{user_context}\n{text}".strip())
        if date_range:
            args["fecha_inicio"], args["fecha_fin"] = date_range
        return {"tool": "crm_dashboard_resumen", "args": args, "user_text": text}

    if "crm_dashboard_whatsapp" in allowed and re.search(
        r"whatsapp|wsp|wa\b",
        text,
        re.IGNORECASE,
    ) and re.search(r"dashboard|m[eé]trica|resumen|chats?|mensajes?", text, re.IGNORECASE):
        args = {}
        date_range = extract_date_range(full_context)
        if date_range:
            args["fecha_inicio"], args["fecha_fin"] = date_range
        return {"tool": "crm_dashboard_whatsapp", "args": args, "user_text": text}

    if "crm_dashboard_tipologico" in allowed and re.search(
        r"tipol[oó]g",
        text,
        re.IGNORECASE,
    ):
        args = {}
        date_range = extract_date_range(full_context)
        if date_range:
            args["fecha_inicio"], args["fecha_fin"] = date_range
        return {"tool": "crm_dashboard_tipologico", "args": args, "user_text": text}

    if "crm_reporte_estados_agentes" in allowed and re.search(
        r"estados?\s+(?:de\s+)?agentes?|auditor[ií]a\s+agentes?|agentes?\s+online|pausas?",
        text,
        re.IGNORECASE,
    ):
        args = {}
        date_range = extract_date_range(full_context)
        if date_range:
            args["fecha_inicio"], args["fecha_fin"] = date_range
        agente = re.search(r"(?:asesor|agente)\s+([^\n,.?!]+)", text, re.IGNORECASE)
        if agente:
            args["agente"] = agente.group(1).strip()
        return {"tool": "crm_reporte_estados_agentes", "args": args, "user_text": text}

    if "crm_listar_conexiones" in allowed and re.search(
        r"conexiones?|canales?\s+activos?",
        text,
        re.IGNORECASE,
    ):
        return {"tool": "crm_listar_conexiones", "args": {}, "user_text": text}

    if "crm_listar_arboles_tipificacion" in allowed and re.search(
        r"[aá]rbol(?:es)?\s+(?:de\s+)?tipific|tipificaci[oó]n",
        text,
        re.IGNORECASE,
    ):
        args = {}
        nombre = re.search(r"tipificaci[oó]n\s+([^\n,.?!]+)", text, re.IGNORECASE)
        if nombre:
            args["nombre"] = nombre.group(1).strip()
        return {"tool": "crm_listar_arboles_tipificacion", "args": args, "user_text": text}

    if "crm_arbol_capas" in allowed and re.search(
        r"capas?|cat[aá]logos?\s+(?:del?\s+)?[aá]rbol",
        text,
        re.IGNORECASE,
    ):
        args: dict[str, Any] = {}
        tree_uuid = re.search(
            r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
            text,
            re.IGNORECASE,
        )
        if tree_uuid:
            args["tree_id"] = tree_uuid.group(1)
        else:
            nombre_arbol = re.search(r"[aá]rbol\s+([^\n,.?!]+)", text, re.IGNORECASE)
            if nombre_arbol:
                args["nombre_arbol"] = nombre_arbol.group(1).strip()
        if args:
            return {"tool": "crm_arbol_capas", "args": args, "user_text": text}

    if "crm_listar_flujos" in allowed and re.search(r"flujos?", text, re.IGNORECASE):
        args: dict[str, Any] = {}
        tree_uuid = re.search(
            r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
            text,
            re.IGNORECASE,
        )
        if tree_uuid:
            args["tree_id"] = tree_uuid.group(1)
        else:
            nombre_arbol = re.search(r"(?:del?\s+)?[aá]rbol\s+([^\n,.?!]+)", text, re.IGNORECASE)
            if nombre_arbol:
                args["nombre_arbol"] = nombre_arbol.group(1).strip()
        flujo = re.search(r"flujo\s+([^\n,.?!]+)", text, re.IGNORECASE)
        if flujo:
            args["nombre_flujo"] = flujo.group(1).strip()
        if args:
            return {"tool": "crm_listar_flujos", "args": args, "user_text": text}

    if "crm_buscar_items_capa" in allowed and re.search(
        r"(?:capa|cat[aá]logo|item|ítem).{0,30}busca",
        text,
        re.IGNORECASE,
    ):
        args: dict[str, Any] = {}
        capa = re.search(r"capa\s+([^\n,.?!]+)", text, re.IGNORECASE)
        if capa:
            args["nombre_capa"] = capa.group(1).strip()
        query = re.search(r"(?:busca(?:r|a)|item)\s+([^\n,.?!]+)", text, re.IGNORECASE)
        if query:
            args["query"] = query.group(1).strip()
        if args:
            return {"tool": "crm_buscar_items_capa", "args": args, "user_text": text}

    if "crm_buscar_clientes" in allowed and re.search(
        r"busca(?:r|a).{0,40}cliente|cliente.{0,40}\d|documento|c[eé]dula",
        text,
        re.IGNORECASE,
    ):
        args: dict[str, Any] = {}
        if doc_match:
            args["documento"] = doc_match
        else:
            name = re.search(r"cliente\s+([^\n,.?!]+)", text, re.IGNORECASE)
            if name:
                args["query"] = name.group(1).strip()
        if args:
            return {"tool": "crm_buscar_clientes", "args": args, "user_text": text}

    if "crm_buscar_usuarios" in allowed and re.search(
        r"busca(?:r|a).{0,40}usuario|agente|asesor",
        text,
        re.IGNORECASE,
    ):
        args: dict[str, Any] = {}
        if doc_match:
            args["query"] = doc_match
        else:
            name = re.search(r"usuario\s+([^\n,.?!]+)", text, re.IGNORECASE)
            if name:
                args["query"] = name.group(1).strip()
        if args:
            return {"tool": "crm_buscar_usuarios", "args": args, "user_text": text}

    if "crm_resumen_estadisticas" in allowed and re.search(
        r"resumen|estad[ií]stica|m[eé]trica",
        text,
        re.IGNORECASE,
    ) and not re.search(r"llamad|reporte|dashboard", text, re.IGNORECASE):
        date_range = extract_date_range(f"{user_context}\n{text}".strip())
        if date_range and "crm_dashboard_resumen" in allowed:
            return {
                "tool": "crm_dashboard_resumen",
                "args": {"fecha_inicio": date_range[0], "fecha_fin": date_range[1]},
                "user_text": text,
            }
        return {"tool": "crm_resumen_estadisticas", "args": {}, "user_text": text}

    # ── Qontrol reportes (sin Excel) ──────────────────────────────────────────
    if "obtener_reporte_estadisticas" in allowed and re.search(
        r"reporte|estad[ií]stica|m[eé]trica|promedio|sentimiento|resumen",
        text,
        re.IGNORECASE,
    ) and re.search(r"llamad", text, re.IGNORECASE) and "excel" not in text.lower():
        args: dict[str, Any] = {}
        date_range = extract_date_range(full_context)
        if date_range:
            args["fecha_inicio"], args["fecha_fin"] = date_range
        campaign_name, _exact = extract_campaign_filter(user_context)
        if campaign_name:
            args["campana"] = campaign_name
        agente = re.search(r"(?:asesor|agente)\s+([^\n,.?!]+)", text, re.IGNORECASE)
        if agente:
            args["agente"] = agente.group(1).strip()
        return {"tool": "obtener_reporte_estadisticas", "args": args, "user_text": text}

    if "buscar_llamadas" in allowed and re.search(
        r"llamad",
        text,
        re.IGNORECASE,
    ) and call_id is None and not re.search(r"transcrip|evaluaci", text, re.IGNORECASE):
        args: dict[str, Any] = {}
        date_range = extract_date_range(full_context)
        if date_range:
            args["fecha_inicio"], args["fecha_fin"] = date_range
        campaign_name, _exact = extract_campaign_filter(user_context)
        if campaign_name:
            args["campana"] = campaign_name
        cliente = re.search(r"cliente\s+([^\n,.?!]+)", text, re.IGNORECASE)
        if cliente:
            args["cliente"] = cliente.group(1).strip()
        limite_match = re.search(r"(?:limite|l[ií]mite|top)\s+(\d+)", text, re.IGNORECASE)
        if limite_match:
            args["limite"] = int(limite_match.group(1))
        if args or re.search(r"busca(?:r|a)|listar?|muestra|dame", text, re.IGNORECASE):
            return {"tool": "buscar_llamadas", "args": args, "user_text": text}

    return None


def run_sync_tool(
    intent: dict[str, Any],
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if intent.get("type") == "clarify":
        return {
            "message": intent["message"],
            "model_used": "tool",
            "tool_calls": None,
            "files": None,
            "pending_job": None,
        }

    tool = intent["tool"]
    args = intent["args"]
    user_text = intent.get("user_text") or _last_user_text(messages or [])
    context_text = combined_user_context(messages or [])

    try:
        raw = execute_tool(tool, args)
    except Exception as error:
        host_hint = ""
        if tool.startswith("crm_"):
            from tools.crm_db import crm_error_hint, get_crm_connection_info

            info = get_crm_connection_info()
            host_hint = (
                f"\n\n**Diagnóstico CRM:** `{info['host']}:{info['port']}/{info['db']}` "
                f"(usuario `{info['user']}`, fuente: {info['source']}).\n"
                f"{crm_error_hint(error)}"
            )
        return {
            "message": f"No pude ejecutar **{tool}**: {error}.{host_hint}",
            "model_used": "tool",
            "tool_calls": None,
            "files": None,
            "pending_job": None,
        }

    message = _format_tool_result(
        tool,
        raw,
        user_text=user_text,
        context_text=context_text,
    )
    return {
        "message": message,
        "model_used": "tool",
        "tool_calls": [{"name": tool, "arguments": args, "result": raw}],
        "files": _tool_result_files(raw),
        "pending_job": None,
    }
