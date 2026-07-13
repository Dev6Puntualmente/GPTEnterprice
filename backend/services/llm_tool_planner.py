from __future__ import annotations

import json
import logging
import re
from typing import Any

from services.agent import run_agent
from services.agent_types import AgentHandoff, ImmediateResult, ProgressCallback, StreamHandoff
from services.synthesis import build_synthesis_system
from services.sync_tools import run_sync_tool

logger = logging.getLogger("gptenterprice.agent")

_PLANNER_INSTRUCTIONS = """
Eres un agente con herramientas (function calling). El usuario pide datos o acciones del sistema.

REGLAS OBLIGATORIAS:
1. Si la pregunta requiere datos reales del CRM, llamadas, reportes, etc. → DEBES usar una herramienta.
2. NUNCA escribas SQL ni pseudo-código en la respuesta final. NUNCA expliques "puedes usar la función X" — EJECÚTALA tú.
3. Si piden Excel, exportar o reporte → exportar_excel_salescloser(query_sql). Si no conoces columnas → obtener_esquema_salescloser.
4. NUNCA digas que "el backend generará" un archivo sin action tool.
5. Responde ÚNICAMENTE con un JSON válido en una sola línea (sin markdown):

Para ejecutar herramienta:
{"action":"tool","tool":"<nombre_exacto>","args":{...}}

Solo para saludos o preguntas conceptuales sin datos (ej. "¿qué es Excel?"):
{"action":"answer","message":"tu respuesta en español"}

Herramientas disponibles (usa el nombre exacto):
{tool_catalog}
"""


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if str(message.get("role", "")).lower() == "user":
            return str(message.get("content", "")).strip()
    return ""


def _format_tool_catalog(tools: list[dict[str, Any]] | None) -> str:
    lines: list[str] = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        description = fn.get("description") or ""
        params = fn.get("parameters") or {}
        props = params.get("properties") if isinstance(params, dict) else {}
        prop_names = ", ".join(props.keys()) if isinstance(props, dict) else ""
        lines.append(f"- {name}: {description}" + (f" (args: {prop_names})" if prop_names else ""))
    return "\n".join(lines) if lines else "(ninguna)"


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


def _allowed_tool_names(tools: list[dict[str, Any]] | None) -> set[str]:
    names: set[str] = set()
    for tool in tools or []:
        if isinstance(tool, dict):
            fn = tool.get("function") or {}
            name = fn.get("name")
            if name:
                names.add(str(name))
    return names


def _synthesize_with_llm(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tool_message: str,
    vllm: dict[str, Any] | None,
    *,
    sync_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    augmented_system = build_synthesis_system(system_prompt, tool_message)
    result = run_agent(
        messages=messages,
        system_prompt=augmented_system,
        tools=None,
        vllm=vllm,
    )
    if isinstance(result, (StreamHandoff, ImmediateResult)):
        result = finalize_handoff_from_agent_result(result, sync_meta)
    if sync_meta:
        result["tool_calls"] = sync_meta.get("tool_calls")
        result["files"] = sync_meta.get("files")
    return result


def finalize_handoff_from_agent_result(
    result: AgentHandoff,
    sync_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(result, ImmediateResult):
        payload = {
            "message": result.message,
            "model_used": result.model_used,
            "tool_calls": result.tool_calls,
            "files": result.files,
        }
    else:
        from services.agent import finalize_handoff

        payload = finalize_handoff(result)
    if sync_meta:
        payload["tool_calls"] = sync_meta.get("tool_calls")
        payload["files"] = sync_meta.get("files")
    return payload


def _synthesize_handoff(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tool_message: str,
    vllm: dict[str, Any] | None,
    *,
    sync_meta: dict[str, Any] | None = None,
) -> StreamHandoff:
    handoff = StreamHandoff(
        messages=messages,
        system_prompt=build_synthesis_system(system_prompt, tool_message),
        model_used="planner",
        tool_calls=sync_meta.get("tool_calls") if sync_meta else None,
        files=sync_meta.get("files") if sync_meta else None,
    )
    if vllm and vllm.get("model"):
        handoff.model_used = str(vllm["model"])
    return handoff


def run_llm_tool_planner(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None,
    vllm: dict[str, Any] | None = None,
    *,
    on_status: ProgressCallback | None = None,
    stream_handoff: bool = False,
) -> dict[str, Any] | AgentHandoff:
    """
    El LLM elige herramienta vía JSON estructurado (sin regex).
    Fallback cuando vLLM no soporta tool-calling nativo (501).
    """
    allowed = _allowed_tool_names(tools)
    if not allowed:
        result = run_agent(
            messages=messages,
            system_prompt=system_prompt,
            tools=None,
            vllm=vllm,
            on_status=on_status,
            stream_handoff=stream_handoff,
        )
        if isinstance(result, AgentHandoff):
            return result
        return result

    catalog = _format_tool_catalog(tools)
    planner_system = _PLANNER_INSTRUCTIONS.format(tool_catalog=catalog)
    from services.chat_context import slim_system_prompt

    slim_project = slim_system_prompt(system_prompt.strip(), drop_project_context=True)
    full_system = f"{planner_system.strip()}\n\n---\nContexto del proyecto:\n{slim_project}"

    if on_status:
        on_status("El modelo está eligiendo la herramienta adecuada...")
    logger.info("LLM planificador: eligiendo herramienta entre %d tools", len(allowed))
    plan = run_agent(messages=messages, system_prompt=full_system, tools=None, vllm=vllm)
    parsed = _extract_json_object(plan.get("message") or "") if isinstance(plan, dict) else None

    if not parsed:
        logger.warning("LLM planificador no devolvió JSON; reintento estricto")
        if on_status:
            on_status("Reintentando selección de herramienta...")
        retry_system = (
            full_system
            + "\n\nIMPORTANTE: Tu respuesta anterior no fue JSON válido. "
            'Responde SOLO con {"action":"tool",...} o {"action":"answer",...}'
        )
        plan = run_agent(messages=messages, system_prompt=retry_system, tools=None, vllm=vllm)
        parsed = _extract_json_object(plan.get("message") or "") if isinstance(plan, dict) else None

    if not parsed:
        return ImmediateResult(
            message=(
                "No pude interpretar qué herramienta usar. "
                "Reformula tu pedido o verifica que el servidor vLLM tenga "
                "--tool-call-parser hermes para tool-calling nativo."
            ),
            model_used=plan.get("model_used") if isinstance(plan, dict) else "planner",
        )

    action = str(parsed.get("action", "")).lower()
    if action == "answer":
        message = str(parsed.get("message") or "").strip()
        return ImmediateResult(
            message=message or "Listo.",
            model_used=plan.get("model_used") if isinstance(plan, dict) else "planner",
        )

    if action != "tool":
        return ImmediateResult(
            message="Respuesta del planificador inválida. Intenta de nuevo.",
            model_used=plan.get("model_used") if isinstance(plan, dict) else "planner",
        )

    tool_name = str(parsed.get("tool") or "").strip()
    args = parsed.get("args") if isinstance(parsed.get("args"), dict) else {}

    if tool_name not in allowed:
        logger.warning("LLM eligió tool no permitida: %s", tool_name)
        return ImmediateResult(
            message=f"El modelo eligió una herramienta no disponible: `{tool_name}`. Intenta de nuevo.",
            model_used=plan.get("model_used") if isinstance(plan, dict) else "planner",
        )

    logger.info("LLM planificador eligió: %s args=%s", tool_name, args)
    if on_status:
        on_status(f"Ejecutando {tool_name.replace('_', ' ')}...")
    user_text = _last_user_text(messages)
    intent = {"tool": tool_name, "args": args, "user_text": user_text}
    sync_result = run_sync_tool(intent, messages)
    if on_status:
        on_status(f"Listo: {tool_name.replace('_', ' ')}")
    if stream_handoff:
        return _synthesize_handoff(
            messages,
            system_prompt,
            sync_result["message"],
            vllm,
            sync_meta=sync_result,
        )
    return _synthesize_with_llm(
        messages,
        system_prompt,
        sync_result["message"],
        vllm,
        sync_meta=sync_result,
    )
