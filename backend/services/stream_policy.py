from __future__ import annotations

import re
from typing import Any

from config import settings

_GENERAL_ONLY = (
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
    for message in reversed(messages):
        if str(message.get("role", "")).lower() == "user":
            return str(message.get("content", "")).strip()
    return ""


def _is_general_question(text: str) -> bool:
    lowered = text.lower().strip()
    return any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _GENERAL_ONLY)


def resolve_effective_stream(
    stream_requested: bool,
    messages: list[dict[str, Any]],
    tool_names: list[str],
) -> bool:
    """
    - Charla general → streaming directo del LLM (sin tools).
    - Resto (con tools en el proyecto) → agente LLM + tools.
    """
    if not stream_requested:
        return False

    if settings.vllm_tools_enabled and tool_names:
        if not _is_general_question(_last_user_text(messages)):
            return False

    if settings.use_sync_tools:
        from services.sync_tools import detect_sync_tool_intent

        if detect_sync_tool_intent(messages, tool_names):
            return True

    return True
