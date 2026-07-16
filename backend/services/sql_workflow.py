from __future__ import annotations

import re
from typing import Any

SCHEMA_TOOL = "obtener_esquema_salescloser"
QUERY_TOOLS = frozenset(
    {
        "ejecutar_consulta_salescloser",
        "exportar_excel_salescloser",
    }
)

_SQL_WORKFLOW_PATTERNS = (
    r"\bcriterio",
    r"\bcampaña\b",
    r"\bcampana\b",
    r"\bmenos\s+de\s+\d+",
    r"\bmás\s+de\s+\d+",
    r"\bmas\s+de\s+\d+",
    r"\bcu[aá]nt",
    r"\btotal\b",
    r"\blistar\b",
    r"\bcategor",
    r"\bsql\b",
    r"\bconsulta\b",
    r"\bagrup",
    r"\bjoin\b",
    r"\bexcel\b",
    r"\bexportar\b",
    r"\by\s+dame\b",
    r"\badem[aá]s\b",
)


def _tool_name(tool: dict[str, Any]) -> str:
    fn = tool.get("function") or {}
    return str(fn.get("name") or "")


def message_needs_sql_workflow(text: str) -> bool:
    """
    True cuando la petición conviene resolver con esquema + SQL
    (consultas compuestas, agregaciones, listados analíticos).
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
    return parts >= 2


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
    Restringe tools visibles al LLM según el flujo esquema → SQL.
    """
    if not all_tools:
        return None
    if not message_needs_sql_workflow(user_text):
        return all_tools

    if not schema_fetched(executed_tools):
        schema_only = [tool for tool in all_tools if _tool_name(tool) == SCHEMA_TOOL]
        return schema_only or all_tools

    allowed_names = {SCHEMA_TOOL, *QUERY_TOOLS}
    filtered = [tool for tool in all_tools if _tool_name(tool) in allowed_names]
    return filtered or all_tools


def needs_more_sql_steps(user_text: str, executed_tools: list[dict[str, Any]] | None) -> bool:
    if not message_needs_sql_workflow(user_text):
        return False
    return len(executed_tools or []) < minimum_tool_steps(user_text)
