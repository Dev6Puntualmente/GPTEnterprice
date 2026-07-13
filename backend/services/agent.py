from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from config import settings
from services.agent_types import AgentHandoff, ImmediateResult, ProgressCallback, StreamHandoff
from services.chat_context import messages_for_synthesis, truncate_tool_result
from services.intent import message_needs_data_tools
from services.synthesis import build_focused_synthesis_system
from tools.registry import execute_tool

logger = logging.getLogger("gptenterprice.agent")


def _build_client(base_url: str, api_key: str | None = None) -> OpenAI:
    key = api_key or settings.bearer_api_key or "not-needed"
    return OpenAI(
        base_url=base_url,
        api_key=key,
        timeout=60.0,
        max_retries=1,
    )


def _endpoint_from_override(
    override: dict[str, Any] | None,
    fallback_url: str,
    fallback_model: str,
    fallback_key: str | None = None,
) -> tuple[str, str, str | None]:
    if not override:
        return fallback_url, fallback_model, fallback_key or settings.bearer_api_key

    api_key = override.get("api_key") or fallback_key or settings.bearer_api_key
    if isinstance(api_key, str) and not api_key.strip():
        api_key = fallback_key or settings.bearer_api_key
    return (
        override.get("base_url") or fallback_url,
        override.get("model") or fallback_model,
        api_key,
    )


def _normalize_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    return tools


def _emit_status(on_status: ProgressCallback | None, message: str) -> None:
    if on_status:
        on_status(message)


def _tool_label(tool_name: str) -> str:
    try:
        from tools.registry import TOOL_CATALOG

        entry = TOOL_CATALOG.get(tool_name, tool_name)
        if "—" in entry:
            return entry.split("—", 1)[1].strip()
        if " - " in entry:
            return entry.split(" - ", 1)[1].strip()
    except Exception:
        pass
    return tool_name.replace("_", " ")


def _conversation_messages(conversation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [message for message in conversation if message.get("role") != "system"]


def _finalize_agent_result(
    message: str,
    model: str,
    executed_tools: list[dict[str, Any]],
    files: list[str],
) -> dict[str, Any]:
    return {
        "message": message,
        "model_used": model,
        "tool_calls": executed_tools or None,
        "files": files or None,
    }


def _run_agent_loop(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None,
    vllm: dict[str, Any] | None,
    *,
    on_status: ProgressCallback | None = None,
    stream_handoff: bool = False,
) -> dict[str, Any] | AgentHandoff:
    base_url, model, api_key = _endpoint_from_override(
        vllm,
        settings.vllm_url,
        settings.vllm_model,
        settings.bearer_api_key,
    )
    client = _build_client(base_url, api_key)

    conversation: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}, *messages]
    openai_tools = _normalize_tools(tools) if settings.vllm_tools_enabled else None
    executed_tools: list[dict[str, Any]] = []
    files: list[str] = []

    _emit_status(on_status, "Analizando tu solicitud...")
    last_user_text = ""
    for message in reversed(messages):
        if str(message.get("role", "")).lower() == "user":
            last_user_text = str(message.get("content", "")).strip()
            break
    requires_tools = bool(openai_tools) and message_needs_data_tools(last_user_text)

    for _ in range(settings.max_tool_iterations):
        if stream_handoff and executed_tools:
            _emit_status(on_status, "Generando respuesta con los datos obtenidos...")
            return StreamHandoff(
                messages=messages_for_synthesis(messages),
                system_prompt=build_focused_synthesis_system(
                    system_prompt,
                    messages,
                    executed_tools,
                ),
                model_used=model,
                tool_calls=executed_tools or None,
                files=files or None,
            )

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": conversation,
            "temperature": 0.2,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools
            if not executed_tools and requires_tools:
                kwargs["tool_choice"] = "required"
            else:
                kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        if choice.tool_calls:
            tool_names = [tool_call.function.name for tool_call in choice.tool_calls]
            logger.info("LLM solicitó tools: %s", tool_names)
            labels = ", ".join(_tool_label(name) for name in tool_names)
            _emit_status(on_status, f"Consultando: {labels}...")

            conversation.append(
                {
                    "role": "assistant",
                    "content": choice.content or "",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in choice.tool_calls
                    ],
                }
            )

            for tool_call in choice.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                _emit_status(on_status, f"Ejecutando {_tool_label(tool_name)}...")
                raw_result = execute_tool(tool_name, arguments)
                result = truncate_tool_result(raw_result)
                executed_tools.append(
                    {
                        "name": tool_name,
                        "arguments": arguments,
                        "result": result,
                    }
                )

                try:
                    parsed = json.loads(result)
                    if isinstance(parsed, dict) and parsed.get("url"):
                        files.append(str(parsed["url"]))
                except json.JSONDecodeError:
                    pass

                _emit_status(on_status, f"Listo: {_tool_label(tool_name)}")
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": result,
                    }
                )
            continue

        final_message = choice.content or "Listo."
        if stream_handoff:
            if executed_tools:
                return StreamHandoff(
                    messages=_conversation_messages(conversation),
                    system_prompt=system_prompt,
                    model_used=model,
                    tool_calls=executed_tools or None,
                    files=files or None,
                )
            logger.warning(
                "LLM respondió en texto sin invocar tools (stream_handoff); se delegará al planificador"
            )
            return ImmediateResult(
                message=final_message,
                model_used=model,
                tool_calls=None,
                files=None,
            )
        return _finalize_agent_result(final_message, model, executed_tools, files)

    limit_message = "Alcancé el límite de iteraciones de herramientas. Intenta simplificar la solicitud."
    if stream_handoff:
        return ImmediateResult(
            message=limit_message,
            model_used=model,
            tool_calls=executed_tools or None,
            files=files or None,
        )
    return _finalize_agent_result(limit_message, model, executed_tools, files)


def run_agent(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None = None,
    vllm: dict[str, Any] | None = None,
    *,
    on_status: ProgressCallback | None = None,
    stream_handoff: bool = False,
) -> dict[str, Any] | AgentHandoff:
    return _run_agent_loop(
        messages,
        system_prompt,
        tools,
        vllm,
        on_status=on_status,
        stream_handoff=stream_handoff,
    )


def finalize_handoff(
    handoff: StreamHandoff,
    vllm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ejecuta la síntesis final sin streaming (ruta JSON)."""
    result = run_agent(
        messages=handoff.messages,
        system_prompt=handoff.system_prompt,
        tools=None,
        vllm=vllm,
    )
    if isinstance(result, dict):
        if handoff.tool_calls and not result.get("tool_calls"):
            result["tool_calls"] = handoff.tool_calls
        if handoff.files and not result.get("files"):
            result["files"] = handoff.files
        if not result.get("model_used"):
            result["model_used"] = handoff.model_used
        return result
    if isinstance(result, ImmediateResult):
        return {
            "message": result.message,
            "model_used": result.model_used or handoff.model_used,
            "tool_calls": handoff.tool_calls,
            "files": handoff.files,
        }
    return finalize_handoff(result, vllm)


def stream_agent(
    messages: list[dict[str, Any]],
    system_prompt: str,
    vllm: dict[str, Any] | None = None,
):
    """Generador de tokens del LLM (sin herramientas)."""
    base_url, model, api_key = _endpoint_from_override(
        vllm,
        settings.vllm_url,
        settings.vllm_model,
        settings.bearer_api_key,
    )
    client = _build_client(base_url, api_key)
    conversation: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *messages,
    ]

    stream = client.chat.completions.create(
        model=model,
        messages=conversation,
        temperature=0.2,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
