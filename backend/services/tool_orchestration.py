from __future__ import annotations

import logging
from typing import Any

from openai import BadRequestError, InternalServerError

from config import settings
from services.agent import run_agent
from services.llm_tool_planner import run_llm_tool_planner

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
    if settings.use_sync_tools:
        from services.sync_tools import detect_sync_tool_intent, run_sync_tool

        intent = detect_sync_tool_intent(messages, tool_names or [])
        if intent:
            kind = intent.get("type") or intent.get("tool")
            logger.info("sync legacy: %s", kind)
            sync_result = run_sync_tool(intent, messages)
            from services.llm_tool_planner import _synthesize_with_llm

            return _synthesize_with_llm(
                messages,
                system_prompt,
                sync_result["message"],
                vllm,
                sync_meta=sync_result,
            )

    if _should_try_native_tools(tools):
        try:
            result = run_agent(
                messages=messages,
                system_prompt=system_prompt,
                tools=tools,
                vllm=vllm,
            )
            global _native_tools_supported
            _native_tools_supported = True
            if result.get("tool_calls"):
                logger.info("LLM usó tools nativas: %s", [t["name"] for t in result["tool_calls"]])
            return result
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
        return run_llm_tool_planner(messages, system_prompt, tools, vllm)

    return run_agent(
        messages=messages,
        system_prompt=system_prompt,
        tools=None,
        vllm=vllm,
    )
