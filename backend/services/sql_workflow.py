from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_TOOL = "obtener_esquema_salescloser"
QUERY_TOOLS = frozenset(
    {
        "ejecutar_consulta_salescloser",
        "ejecutar_consulta_crm",
        "exportar_excel_salescloser",
    }
)

_SQL_WORKFLOW_PATTERNS = (
    r"\bsql\b",
    r"\bselect\b",
    r"\bjoin\b",
    r"\bagrup",
    r"\bexcel\b",
    r"\bxlsx\b",
    r"\bexportar\b",
    r"\bmenos\s+de\s+\d+\s+criterios?",
    r"\by\s+dame\b",
    r"\badem[aá]s\b",
)


def _tool_name(tool: dict[str, Any]) -> str:
    fn = tool.get("function") or {}
    return str(fn.get("name") or "")


def _tool_names(all_tools: list[dict[str, Any]] | None) -> set[str]:
    return {_tool_name(tool) for tool in (all_tools or []) if _tool_name(tool)}


def detect_dedicated_tool_intent(
    text: str,
    all_tools: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Intent de herramienta dedicada (no SQL) si el mensaje encaja."""
    if not all_tools:
        return None
    from services.sync_tools import detect_sync_tool_intent

    allowed = list(_tool_names(all_tools))
    if not allowed:
        return None
    return detect_sync_tool_intent([{"role": "user", "content": text}], allowed)


def dedicated_tool_covers_request(
    text: str,
    all_tools: list[dict[str, Any]] | None,
) -> bool:
    intent = detect_dedicated_tool_intent(text, all_tools)
    if not intent:
        return False
    tool = str(intent.get("tool") or "")
    return tool not in QUERY_TOOLS and tool != SCHEMA_TOOL


def _dedicated_tool_failed(tool_name: str, executed_tools: list[dict[str, Any]] | None) -> bool:
    for item in executed_tools or []:
        if item.get("name") != tool_name:
            continue
        raw = str(item.get("result") or "")
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and parsed.get("success") is False:
                return True
        except json.JSONDecodeError:
            if "error" in raw.lower() or "fail" in raw.lower():
                return True
        return False
    return False


def message_needs_sql_workflow(text: str) -> bool:
    """
    True cuando la petición podría resolverse con esquema + SQL
    (consultas analíticas, exportaciones, agregaciones sin tool dedicada).
    """
    lowered = text.lower().strip()
    if not lowered:
        return False
    if re.search(r"\b(borra|elimina|delete)\b", lowered):
        return False
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in _SQL_WORKFLOW_PATTERNS):
        return True
    parts = 1
    for pattern in (r"\badem[aá]s\b", r"\by\s+dame\b", r";"):
        parts += len(re.findall(pattern, lowered))
    return parts >= 3


def should_use_sql_workflow(
    text: str,
    all_tools: list[dict[str, Any]] | None = None,
    executed_tools: list[dict[str, Any]] | None = None,
) -> bool:
    """
    SQL solo cuando hace falta: primero herramientas dedicadas; SQL como respaldo.
    """
    if not message_needs_sql_workflow(text):
        return False

    intent = detect_dedicated_tool_intent(text, all_tools)
    if intent:
        tool = str(intent.get("tool") or "")
        if tool not in QUERY_TOOLS and tool != SCHEMA_TOOL:
            tried = {item.get("name") for item in (executed_tools or [])}
            if tool not in tried:
                return False
            if not _dedicated_tool_failed(tool, executed_tools):
                return False

    lowered = text.lower()
    if re.search(r"\b(sql|select|excel|xlsx|exportar)\b", lowered):
        return True

    if re.search(r"\bmenos\s+de\s+\d+\s+criterios?\b", lowered):
        names = _tool_names(all_tools)
        if "listar_campanas_con_pocos_criterios" in names and not _dedicated_tool_failed(
            "listar_campanas_con_pocos_criterios",
            executed_tools,
        ):
            if "listar_campanas_con_pocos_criterios" not in {
                item.get("name") for item in (executed_tools or [])
            }:
                return False

    return not dedicated_tool_covers_request(text, all_tools)


def schema_fetched(executed_tools: list[dict[str, Any]] | None) -> bool:
    return any(item.get("name") == SCHEMA_TOOL for item in (executed_tools or []))


def query_executions(executed_tools: list[dict[str, Any]] | None) -> int:
    return sum(1 for item in (executed_tools or []) if item.get("name") in QUERY_TOOLS)


def minimum_tool_steps(text: str) -> int:
    """Pasos mínimos: 1 esquema + N consultas (una por parte del pedido)."""
    from services.intent import estimate_user_request_parts

    if not message_needs_sql_workflow(text):
        return 1
    return 1 + estimate_user_request_parts(text)


def tools_for_turn(
    all_tools: list[dict[str, Any]] | None,
    executed_tools: list[dict[str, Any]] | None,
    user_text: str,
) -> list[dict[str, Any]] | None:
    """
    Restringe tools visibles al LLM solo durante flujo SQL activo.
    """
    if not all_tools:
        return None
    if not should_use_sql_workflow(user_text, all_tools, executed_tools):
        return all_tools

    if not schema_fetched(executed_tools):
        schema_only = [tool for tool in all_tools if _tool_name(tool) == SCHEMA_TOOL]
        return schema_only or all_tools

    allowed_names = {SCHEMA_TOOL, *QUERY_TOOLS}
    filtered = [tool for tool in all_tools if _tool_name(tool) in allowed_names]
    return filtered or all_tools


def needs_more_sql_steps(
    user_text: str,
    executed_tools: list[dict[str, Any]] | None,
    all_tools: list[dict[str, Any]] | None = None,
) -> bool:
    if not should_use_sql_workflow(user_text, all_tools, executed_tools):
        return False
    return len(executed_tools or []) < minimum_tool_steps(user_text)
