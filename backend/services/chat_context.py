from __future__ import annotations

import json
from typing import Any

CONTEXT_BLOCK_MARKER = "Contexto del proyecto:"

DEFAULT_MAX_MESSAGE_CHARS = 2500
DEFAULT_MAX_TOOL_RESULT_CHARS = 8000
DEFAULT_MAX_SYSTEM_PROMPT_CHARS = 10000
DEFAULT_MAX_SYNTHESIS_TOOL_CHARS = 5000
DEFAULT_HISTORY_PER_ROLE = 2

_HEAVY_TOOL_KEYS = (
    "transcripcion",
    "segmentos",
    "chat_whatsapp",
    "mensajes",
    "coaching",
    "detalles_llamadas",
    "resultados",
    "evaluation_data",
    "ai_evaluation",
    "acoustic_analysis",
    "acustica",
    "callgist",
)


def truncate_text(text: str, max_chars: int, suffix: str = "...[truncado]") -> str:
    if not text or len(text) <= max_chars:
        return text or ""
    keep = max(0, max_chars - len(suffix))
    return text[:keep] + suffix


def slim_system_prompt(
    system_prompt: str,
    *,
    max_chars: int = DEFAULT_MAX_SYSTEM_PROMPT_CHARS,
    drop_project_context: bool = False,
) -> str:
    text = (system_prompt or "").strip()
    if drop_project_context and CONTEXT_BLOCK_MARKER in text:
        text = text.split(CONTEXT_BLOCK_MARKER, 1)[0].rstrip()
    return truncate_text(text, max_chars)


def _truncate_message_content(
    message: dict[str, Any],
    max_chars: int,
) -> dict[str, Any]:
    role = str(message.get("role", "")).lower()
    if role not in ("user", "assistant"):
        return message
    content = str(message.get("content", "") or "")
    if len(content) <= max_chars:
        return message
    return {**message, "content": truncate_text(content, max_chars)}


def trim_messages_for_agent(
    messages: list[dict[str, Any]],
    per_role: int = DEFAULT_HISTORY_PER_ROLE,
    max_content_chars: int = DEFAULT_MAX_MESSAGE_CHARS,
) -> list[dict[str, Any]]:
    """Conserva los últimos N mensajes de usuario y N del asistente, truncando contenido largo."""
    users = 0
    assistants = 0
    kept: list[dict[str, Any]] = []

    for message in reversed(messages):
        role = str(message.get("role", "")).lower()
        if role == "user":
            if users >= per_role:
                continue
            users += 1
        elif role == "assistant":
            if assistants >= per_role:
                continue
            assistants += 1
        else:
            continue
        kept.insert(0, _truncate_message_content(message, max_content_chars))

    return kept


def messages_for_synthesis(
    messages: list[dict[str, Any]],
    *,
    max_content_chars: int = DEFAULT_MAX_MESSAGE_CHARS,
) -> list[dict[str, Any]]:
    """Solo el último mensaje del usuario para redactar la respuesta final."""
    for message in reversed(messages):
        if str(message.get("role", "")).lower() == "user":
            return [_truncate_message_content(message, max_content_chars)]
    return []


def _shrink_nested_value(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "[...]"
    if isinstance(value, dict):
        shrunk: dict[str, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if key_lower in _HEAVY_TOOL_KEYS:
                if isinstance(item, list):
                    shrunk[key] = {
                        "total": len(item),
                        "omitido": "contenido pesado recortado para el LLM",
                    }
                elif isinstance(item, dict):
                    shrunk[key] = {
                        "omitido": "contenido pesado recortado para el LLM",
                        "claves": list(item.keys())[:8],
                    }
                else:
                    shrunk[key] = truncate_text(str(item), 400)
                continue
            if key_lower == "prompt" and isinstance(item, str) and len(item) > 600:
                shrunk[key] = truncate_text(item, 600)
                continue
            shrunk[key] = _shrink_nested_value(item, depth + 1)
        return shrunk
    if isinstance(value, list):
        if len(value) > 25:
            head = [_shrink_nested_value(item, depth + 1) for item in value[:10]]
            return head + [{"omitido": f"{len(value) - 10} elementos más"}]
        return [_shrink_nested_value(item, depth + 1) for item in value]
    if isinstance(value, str) and len(value) > 1200:
        return truncate_text(value, 1200)
    return value


def _strip_criterion_prompts(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    criterios = out.get("criterios")
    if isinstance(criterios, list):
        out["criterios"] = [
            {key: value for key, value in item.items() if key != "prompt"}
            if isinstance(item, dict)
            else item
            for item in criterios
        ]
    detalle = out.get("detalle")
    if isinstance(detalle, dict) and isinstance(detalle.get("criterios"), dict):
        resultados = detalle["criterios"].get("resultados")
        if isinstance(resultados, list):
            detalle = dict(detalle)
            detalle["criterios"] = {
                **detalle["criterios"],
                "resultados": resultados[:15],
            }
            out["detalle"] = detalle
    return out


def truncate_tool_result(
    result: str,
    max_chars: int = DEFAULT_MAX_TOOL_RESULT_CHARS,
) -> str:
    if not result or len(result) <= max_chars:
        return result or ""
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            shrunk = _shrink_nested_value(parsed)
            compact = json.dumps(shrunk, ensure_ascii=False)
            if len(compact) <= max_chars:
                return compact
            stripped = _strip_criterion_prompts(shrunk)
            compact = json.dumps(stripped, ensure_ascii=False)
            if len(compact) <= max_chars:
                return compact
            return json.dumps(
                {
                    "success": parsed.get("success"),
                    "mensaje": parsed.get("mensaje"),
                    "call_id": parsed.get("call_id"),
                    "cliente": parsed.get("cliente"),
                    "campana": parsed.get("campana"),
                    "compliance_score": parsed.get("compliance_score"),
                    "sentimiento": parsed.get("sentimiento"),
                    "resumen": parsed.get("resumen"),
                    "puntos_clave": parsed.get("puntos_clave"),
                    "url": parsed.get("url"),
                    "total": parsed.get("total") or parsed.get("total_filas") or parsed.get("total_llamadas"),
                    "aviso": "Respuesta de herramienta recortada por límite de contexto del modelo",
                },
                ensure_ascii=False,
            )
    except json.JSONDecodeError:
        pass
    return truncate_text(result, max_chars)


def estimate_chars(messages: list[dict[str, Any]], system_prompt: str = "") -> int:
    total = len(system_prompt or "")
    for message in messages:
        total += len(str(message.get("content", "") or ""))
    return total


def log_context_size(
    logger: Any,
    *,
    label: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools_count: int = 0,
) -> None:
    chars = estimate_chars(messages, system_prompt)
    # ~4 chars per token heuristic for Spanish/JSON mix
    approx_tokens = chars // 4
    logger.info(
        "%s: ~%d chars (~%d tokens), mensajes=%d, tools=%d",
        label,
        chars,
        approx_tokens,
        len(messages),
        tools_count,
    )
