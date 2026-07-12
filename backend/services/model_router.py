from __future__ import annotations

import re
from typing import Any

TOOL_KEYWORDS = (
    "reporte",
    "excel",
    "exportar",
    "genera",
    "generar",
    "busca",
    "buscar",
    "consulta",
    "usuario",
    "usuarios",
    "entrada",
    "llegó",
    "llego",
    "hora",
    "entre",
    "desde",
    "hasta",
)


def needs_smart_model(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> bool:
    """Usa Qwen 7B para tools o preguntas complejas; Phi 3.5 para chat rápido."""
    if tools:
        last_user = _last_user_message(messages)
        if last_user and _looks_like_tool_request(last_user):
            return True

    last_user = _last_user_message(messages)
    if not last_user:
        return False

    if _looks_like_tool_request(last_user):
        return True

    if len(last_user.split()) > 40:
        return True

    return False


def _last_user_message(messages: list[dict[str, Any]]) -> str | None:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                return content
    return None


def _looks_like_tool_request(text: str) -> bool:
    lowered = text.lower()
    if any(keyword in lowered for keyword in TOOL_KEYWORDS):
        return True
    if re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?\b", lowered):
        return True
    return False
