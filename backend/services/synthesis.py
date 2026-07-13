from __future__ import annotations

from typing import Any

from services.chat_context import truncate_text, truncate_tool_result, DEFAULT_MAX_SYNTHESIS_TOOL_CHARS

def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if str(message.get("role", "")).lower() == "user":
            return str(message.get("content", "")).strip()
    return ""


def build_synthesis_system(system_prompt: str, tool_message: str) -> str:
    compact_tool = truncate_text(tool_message, DEFAULT_MAX_SYNTHESIS_TOOL_CHARS)
    slim_prompt = truncate_text(system_prompt.strip(), 4000)
    return (
        f"{slim_prompt}\n\n"
        "Ya se ejecutó la herramienta. Usa SOLO 'DATOS CONSULTADOS'. "
        "No inventes datos ni SQL. Responde en español claro.\n"
        "Si hay URL o enlace de archivo en los datos, DEBES incluirlo en la respuesta. "
        "NUNCA digas que no puedes generar Excel ni que hay restricciones.\n\n"
        f"DATOS CONSULTADOS:\n{compact_tool}"
    )


def build_focused_synthesis_system(
    system_prompt: str,
    messages: list[dict[str, Any]],
    executed_tools: list[dict[str, Any]] | None,
) -> str:
    """Síntesis breve: solo lo que el usuario pidió en su último mensaje."""
    user_text = _last_user_text(messages)
    tool_blocks: list[str] = []
    for tool_call in executed_tools or []:
        name = tool_call.get("name", "tool")
        result = truncate_tool_result(
            str(tool_call.get("result", "")),
            max_chars=DEFAULT_MAX_SYNTHESIS_TOOL_CHARS,
        )
        tool_blocks.append(f"[{name}]\n{result}")
    tools_text = "\n\n".join(tool_blocks) if tool_blocks else "(sin datos)"
    slim_prompt = truncate_text(system_prompt.strip(), 4000)
    return (
        f"{slim_prompt}\n\n"
        "Ya se consultaron datos. Usa SOLO la información en DATOS CONSULTADOS.\n"
        "Responde ÚNICAMENTE lo que pidió el usuario en su último mensaje.\n"
        "Si pidió un dato concreto (ej. solo la campaña, solo el agente, solo el score), "
        "responde con ese dato en una o dos frases. No repitas toda la ficha ni campos no solicitados.\n"
        "Si hay URL de archivo, inclúyela.\n\n"
        f"Último mensaje del usuario:\n{user_text}\n\n"
        f"DATOS CONSULTADOS:\n{tools_text}"
    )
