from __future__ import annotations

import re
from typing import Any

from config import settings

# Solo SQL custom requiere tool-calling nativo en vLLM.
_NATIVE_ONLY_HINTS = (
    r"ejecuta(?:r|)\s+(?:una\s+)?consulta\s+sql",
    r"consulta\s+sql\s+select",
    r"select\s+.+\s+from\s+crm\.",
)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if str(message.get("role", "")).lower() == "user":
            return str(message.get("content", "")).strip()
    return ""


def message_needs_native_vllm_tools(
    messages: list[dict[str, Any]],
    tool_names: list[str],
) -> bool:
    """True solo cuando sync/heavy no bastan y hace falta el loop nativo de vLLM."""
    if not settings.vllm_tools_enabled or not tool_names:
        return False
    text = _last_user_text(messages).lower()
    if not text:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in _NATIVE_ONLY_HINTS)


def resolve_effective_stream(
    stream_requested: bool,
    messages: list[dict[str, Any]],
    tool_names: list[str],
) -> bool:
    """
    Híbrido automático:
    - Chat normal → streaming.
    - Sync/heavy tools → el caller emite pseudo-stream; mantener stream_requested.
    - SQL custom / poster sin sync → desactivar stream para tools nativas.
    """
    if not stream_requested:
        return False

    from services.sync_tools import detect_sync_tool_intent

    if detect_sync_tool_intent(messages, tool_names):
        return True

    if message_needs_native_vllm_tools(messages, tool_names):
        return False

    return True
