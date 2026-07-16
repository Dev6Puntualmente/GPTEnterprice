from __future__ import annotations

import logging
from typing import Any

from openai import BadRequestError, InternalServerError

from config import settings
from services.agent import finalize_handoff, run_agent
from services.agent_types import AgentHandoff, ImmediateResult, ProgressCallback, StreamHandoff
from services.llm_tool_planner import finalize_handoff_from_agent_result, run_llm_tool_planner

logger = logging.getLogger("gptenterprice.agent")

_native_tools_supported: bool | None = None


def is_vllm_tools_unsupported(error: Exception) -> bool:
    text = str(error).lower()
    if "501" in text or "not implemented" in text:
        return True
    if "gptosstoolparser" in text or "harmonyparser" in text:
        return True
    if "tool-call-parser" in text or "tool_call_parser" in text:
        return True
    return False


def _mark_native_tools_unsupported(reason: str) -> None:
    global _native_tools_supported
    if _native_tools_supported is not False:
        logger.warning("tool-calling nativo no disponible: %s", reason)
    _native_tools_supported = False


def _should_try_native_tools(tools: list[dict[str, Any]] | None) -> bool:
    global _native_tools_supported
    if not settings.vllm_tools_enabled or not settings.vllm_native_tools or not tools:
        return False
    if _native_tools_supported is False:
        return False
    return True


def _normalize_agent_handoff(result: AgentHandoff | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if isinstance(result, StreamHandoff):
        return finalize_handoff(result)
    return finalize_handoff_from_agent_result(result)


def run_chat_with_tools_handoff(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None,
    tool_names: list[str] | None = None,
    vllm: dict[str, Any] | None = None,
    *,
    on_status: ProgressCallback | None = None,
) -> AgentHandoff:
    """
    Igual que run_chat_with_tools, pero devuelve handoff para streaming real
    en la síntesis final (sin llamar al LLM para redactar todavía).
    """
    if settings.use_sync_tools:
        from services.synthesis import build_synthesis_system
        from services.sync_tools import detect_sync_tool_intent, run_sync_tool

        intent = detect_sync_tool_intent(messages, tool_names or [])
        if intent:
            kind = intent.get("type") or intent.get("tool")
            logger.info("sync legacy: %s", kind)
            if on_status:
                on_status(f"Ejecutando {str(kind).replace('_', ' ')}...")
            sync_result = run_sync_tool(intent, messages)
            if on_status:
                on_status(f"Listo: {str(kind).replace('_', ' ')}")
            return StreamHandoff(
                messages=messages,
                system_prompt=build_synthesis_system(system_prompt, sync_result["message"]),
                model_used="sync",
                tool_calls=sync_result.get("tool_calls"),
                files=sync_result.get("files"),
            )

    if _should_try_native_tools(tools):
        try:
            result = run_agent(
                messages=messages,
                system_prompt=system_prompt,
                tools=tools,
                vllm=vllm,
                on_status=on_status,
                stream_handoff=True,
            )
            global _native_tools_supported
            _native_tools_supported = True

            native_used_tools = False
            if isinstance(result, StreamHandoff) and result.tool_calls:
                native_used_tools = True
                logger.info(
                    "LLM usó tools nativas: %s",
                    [tool["name"] for tool in result.tool_calls],
                )
                return result

            if isinstance(result, ImmediateResult) and not result.tool_calls and result.message:
                logger.warning(
                    "LLM respondió sin tools con mensaje directo; usando planificador LLM"
                )
            elif isinstance(result, ImmediateResult) and not result.tool_calls:
                logger.warning("tool-calling nativo no invocó herramientas; usando planificador LLM")

            if isinstance(result, dict) and result.get("tool_calls"):
                native_used_tools = True
                logger.info(
                    "LLM usó tools nativas: %s",
                    [tool["name"] for tool in result["tool_calls"]],
                )
                return StreamHandoff(
                    messages=messages,
                    system_prompt=system_prompt,
                    model_used=str(result.get("model_used") or "agent"),
                    tool_calls=result.get("tool_calls"),
                    files=result.get("files"),
                )

            if native_used_tools:
                return result  # type: ignore[return-value]

            logger.warning(
                "tool-calling nativo no invocó herramientas; usando planificador LLM"
            )
        except InternalServerError as error:
            if not is_vllm_tools_unsupported(error):
                raise
            _mark_native_tools_unsupported(str(error))
        except BadRequestError as error:
            if not is_vllm_tools_unsupported(error):
                raise
            _mark_native_tools_unsupported(str(error))

    if settings.vllm_tools_enabled and tools:
        logger.info("usando planificador LLM (el modelo elige la herramienta)")
        result = run_llm_tool_planner(
            messages,
            system_prompt,
            tools,
            vllm,
            on_status=on_status,
            stream_handoff=True,
        )
        if isinstance(result, AgentHandoff):
            return result
        return StreamHandoff(
            messages=messages,
            system_prompt=system_prompt,
            model_used=str(result.get("model_used") or "planner"),
            tool_calls=result.get("tool_calls"),
            files=result.get("files"),
        )

    result = run_agent(
        messages=messages,
        system_prompt=system_prompt,
        tools=None,
        vllm=vllm,
        on_status=on_status,
        stream_handoff=True,
    )
    if isinstance(result, AgentHandoff):
        return result
    return ImmediateResult(
        message=str(result.get("message") or "Listo."),
        model_used=str(result.get("model_used") or "agent"),
        tool_calls=result.get("tool_calls"),
        files=result.get("files"),
    )


def run_chat_with_tools(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None,
    tool_names: list[str] | None = None,
    vllm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    1) Tool-calling nativo en vLLM (si el servidor lo soporta).
    2) Si falla (501) → planificador LLM elige la tool (JSON), sin regex.
    3) Legacy sync_tools solo si SYNC_TOOLS_ENABLED=true.
    """
    handoff = run_chat_with_tools_handoff(
        messages,
        system_prompt,
        tools,
        tool_names,
        vllm,
    )
    return _normalize_agent_handoff(handoff)
