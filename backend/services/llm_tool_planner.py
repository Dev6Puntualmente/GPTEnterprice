from __future__ import annotations

import json
import logging
import re
from typing import Any

from services.agent import run_agent
from services.agent_types import AgentHandoff, ImmediateResult, ProgressCallback, StreamHandoff
from services.synthesis import build_synthesis_system
from services.intent import estimate_user_request_parts
from services.sql_workflow import (
    SCHEMA_TOOL,
    message_needs_sql_workflow,
    minimum_tool_steps,
    schema_fetched,
)
from services.sync_tools import run_sync_tool

logger = logging.getLogger("gptenterprice.agent")

_PLANNER_INSTRUCTIONS = """
Eres un agente con herramientas (function calling). El usuario pide datos o acciones del sistema.

_REGLAS OBLIGATORIAS:
1. Si la pregunta requiere datos reales del CRM, llamadas, reportes, etc. → DEBES usar una herramienta.
2. NUNCA escribas SQL ni pseudo-código en la respuesta final. NUNCA expliques "puedes usar la función X" — EJECÚTALA tú.
3. Si el usuario pide VARIAS cosas o datos analíticos → flujo OBLIGATORIO:
   a) obtener_esquema_salescloser (si no está en datos ya obtenidos)
   b) ejecutar_consulta_salescloser — una consulta SELECT por cada parte del pedido
4. NUNCA inventes columnas: calls.id (no call_id), campaigns.name (no campana), supervisor_criteria.categoria.
5. Campañas con menos de N criterios → SQL con GROUP BY + HAVING COUNT(...) < N.
6. Si piden Excel → exportar_excel_salescloser(query_sql) después del esquema.
7. Si piden poster → generar_poster_alerta.
8. Si piden presentación / PowerPoint / PPT / diapositivas → generar_presentacion.
   Imágenes del usuario en archivos/imagenes; sin imágenes → fondos en degradado (no API externa).
9. NUNCA digas que "el backend generará" un archivo sin action tool.
10. Responde ÚNICAMENTE con JSON válido en una sola línea:

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


def _format_executed_for_planner(executed: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in executed:
        name = item.get("name", "tool")
        result = str(item.get("result", ""))[:1200]
        lines.append(f"### {name}\n{result}")
    return "\n\n".join(lines)


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
    base_system = f"{planner_system.strip()}\n\n---\nContexto del proyecto:\n{slim_project}"

    user_text = _last_user_text(messages)
    sql_workflow = message_needs_sql_workflow(user_text)
    request_parts = estimate_user_request_parts(user_text)
    max_steps = min(max(minimum_tool_steps(user_text), 2) if sql_workflow else max(request_parts, 2), 6)

    executed_tool_calls: list[dict[str, Any]] = []
    executed_messages: list[str] = []
    all_files: list[str] = []
    model_used = "planner"

    if sql_workflow and not schema_fetched(executed_tool_calls):
        if on_status:
            on_status("Obteniendo esquema de tablas...")
        logger.info("SQL workflow planificador: auto-ejecutando %s", SCHEMA_TOOL)
        schema_result = run_sync_tool(
            {"tool": SCHEMA_TOOL, "args": {}, "user_text": user_text},
            messages,
        )
        executed_messages.append(str(schema_result.get("message") or ""))
        for call in schema_result.get("tool_calls") or []:
            executed_tool_calls.append(call)

    for step in range(max_steps):
        step_context = ""
        if executed_tool_calls:
            step_context = (
                "\n\n---\nDatos ya obtenidos en este turno:\n"
                f"{_format_executed_for_planner(executed_tool_calls)}\n\n"
            )
            if sql_workflow and schema_fetched(executed_tool_calls):
                step_context += (
                    "El esquema ya está disponible. Usa SOLO ejecutar_consulta_salescloser "
                    "con SELECT válido (una consulta por cada parte del pedido). "
                    'JSON: {"action":"tool","tool":"ejecutar_consulta_salescloser","args":{"query_sql":"..."}}'
                )
            else:
                step_context += (
                    "Si AÚN faltan datos, elige la SIGUIENTE herramienta con action:tool."
                )
        full_system = base_system + step_context

        if on_status:
            on_status(
                f"El modelo elige herramienta ({step + 1}/{max_steps})..."
                if step == 0
                else f"Siguiente herramienta ({step + 1}/{max_steps})..."
            )
        logger.info("LLM planificador paso %d/%d", step + 1, max_steps)
        plan = run_agent(messages=messages, system_prompt=full_system, tools=None, vllm=vllm)
        if isinstance(plan, dict) and plan.get("model_used"):
            model_used = str(plan["model_used"])
        parsed = _extract_json_object(plan.get("message") or "") if isinstance(plan, dict) else None

        if not parsed:
            logger.warning("LLM planificador no devolvió JSON en paso %d", step + 1)
            if step == 0:
                retry_system = (
                    full_system
                    + "\n\nIMPORTANTE: Responde SOLO con "
                    '{"action":"tool",...} o {"action":"answer",...}'
                )
                plan = run_agent(messages=messages, system_prompt=retry_system, tools=None, vllm=vllm)
                parsed = _extract_json_object(plan.get("message") or "") if isinstance(plan, dict) else None
            if not parsed:
                break

        action = str(parsed.get("action", "")).lower()
        if action == "answer":
            if executed_tool_calls:
                break
            message = str(parsed.get("message") or "").strip()
            return ImmediateResult(
                message=message or "Listo.",
                model_used=model_used,
            )

        if action != "tool":
            break

        tool_name = str(parsed.get("tool") or "").strip()
        args = parsed.get("args") if isinstance(parsed.get("args"), dict) else {}
        if tool_name not in allowed:
            logger.warning("LLM eligió tool no permitida: %s", tool_name)
            break

        logger.info("LLM planificador paso %d: %s args=%s", step + 1, tool_name, args)
        if on_status:
            on_status(f"Ejecutando {tool_name.replace('_', ' ')}...")
        intent = {"tool": tool_name, "args": args, "user_text": user_text}
        sync_result = run_sync_tool(intent, messages)
        if on_status:
            on_status(f"Listo: {tool_name.replace('_', ' ')}")

        executed_messages.append(str(sync_result.get("message") or ""))
        for call in sync_result.get("tool_calls") or []:
            executed_tool_calls.append(call)
        for file_url in sync_result.get("files") or []:
            if file_url not in all_files:
                all_files.append(file_url)

        target_steps = minimum_tool_steps(user_text) if sql_workflow else request_parts
        if len(executed_tool_calls) >= target_steps:
            break

    if not executed_tool_calls:
        return ImmediateResult(
            message=(
                "No pude ejecutar las herramientas necesarias. "
                "Reformula tu pedido o verifica tool-calling nativo (--tool-call-parser hermes)."
            ),
            model_used=model_used,
        )

    combined_message = "\n\n".join(msg for msg in executed_messages if msg.strip())
    sync_meta = {
        "tool_calls": executed_tool_calls,
        "files": all_files or None,
    }
    if stream_handoff:
        from services.synthesis import build_focused_synthesis_system

        return StreamHandoff(
            messages=messages,
            system_prompt=build_focused_synthesis_system(
                system_prompt,
                messages,
                executed_tool_calls,
            ),
            model_used=model_used,
            tool_calls=executed_tool_calls,
            files=all_files or None,
        )
    return _synthesize_with_llm(
        messages,
        system_prompt,
        combined_message,
        vllm,
        sync_meta=sync_meta,
    )
