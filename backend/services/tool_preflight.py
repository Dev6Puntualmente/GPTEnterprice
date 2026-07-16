from __future__ import annotations

import json
import logging
import re
from typing import Any

from services.sync_tools import detect_sync_tool_intent, run_sync_tool

logger = logging.getLogger("gptenterprice.agent")

_LIST_CAPAS = re.compile(
    r"capas?\s+(?:del?\s+)?(?:arbol|árbol)|"
    r"(?:listar?|dame|muestra|ver)\s+(?:las?\s+)?capas?",
    re.IGNORECASE,
)


def _tool_names(tools: list[dict[str, Any]] | None) -> list[str]:
    names: list[str] = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") or {}
        name = fn.get("name")
        if name:
            names.append(str(name))
    return names


def preflight_sync_intent(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Si el mensaje encaja con una herramienta dedicada, devuelve el intent (sin ejecutar)."""
    allowed = _tool_names(tools)
    if not allowed:
        return None
    return detect_sync_tool_intent(messages, allowed)


def correct_tool_before_execute(
    tool_name: str,
    arguments: dict[str, Any],
    user_text: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
) -> tuple[str, dict[str, Any]]:
    """
    Corrige elecciones erróneas del LLM (ej. buscar_items cuando pidieron listar capas).
    """
    allowed = _tool_names(tools)
    intent = detect_sync_tool_intent(messages, allowed)
    if not intent:
        return tool_name, arguments

    expected = str(intent.get("tool") or "")
    expected_args = intent.get("args") if isinstance(intent.get("args"), dict) else {}

    if _LIST_CAPAS.search(user_text):
        if tool_name == "crm_buscar_items_capa" and expected == "crm_arbol_capas":
            logger.info("Corrigiendo tool %s → %s (listar capas)", tool_name, expected)
            return expected, expected_args
        if tool_name != "crm_arbol_capas" and expected == "crm_arbol_capas":
            logger.info("Corrigiendo tool %s → %s (árbol/capas)", tool_name, expected)
            return expected, expected_args

    if tool_name != expected and expected in allowed:
        if tool_name in ("crm_buscar_items_capa", "ejecutar_consulta_crm") and expected.startswith("crm_"):
            logger.info("Corrigiendo tool %s → %s (intent dedicado)", tool_name, expected)
            return expected, expected_args

    return tool_name, arguments


def tool_result_failed(raw_result: str) -> bool:
    try:
        parsed = json.loads(raw_result)
        if isinstance(parsed, dict) and parsed.get("success") is False:
            return True
    except json.JSONDecodeError:
        pass
    return False


def format_failed_tool_turn(
    messages: list[dict[str, Any]],
    tool_name: str,
    arguments: dict[str, Any],
    raw_result: str,
) -> str | None:
    """Respuesta directa cuando la tool falló — evita que el LLM invente datos."""
    if not tool_result_failed(raw_result):
        return None
    sync = run_sync_tool(
        {"tool": tool_name, "args": arguments, "user_text": ""},
        messages,
    )
    message = str(sync.get("message") or "").strip()
    if message:
        return message
    try:
        parsed = json.loads(raw_result)
        if isinstance(parsed, dict):
            return parsed.get("mensaje") or parsed.get("error") or "No se pudo obtener los datos del sistema."
    except json.JSONDecodeError:
        pass
    return "No se pudo obtener los datos del sistema."
