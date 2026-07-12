from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from config import settings
from services.model_router import needs_smart_model
from tools.registry import execute_tool


def _build_client(base_url: str) -> OpenAI:
    return OpenAI(base_url=base_url, api_key="not-needed")


def _normalize_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    return tools


def run_agent(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    use_smart = needs_smart_model(messages, tools)
    base_url = settings.vllm_smart_url if use_smart else settings.vllm_fast_url
    model = settings.vllm_smart_model if use_smart else settings.vllm_fast_model
    client = _build_client(base_url)

    conversation: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}, *messages]
    openai_tools = _normalize_tools(tools)
    executed_tools: list[dict[str, Any]] = []
    files: list[str] = []

    for _ in range(settings.max_tool_iterations):
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": conversation,
            "temperature": 0.2,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        if choice.tool_calls:
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

                result = execute_tool(tool_name, arguments)
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
        return {
            "message": final_message,
            "model_used": model,
            "tool_calls": executed_tools or None,
            "files": files or None,
        }

    return {
        "message": "Alcancé el límite de iteraciones de herramientas. Intenta simplificar la solicitud.",
        "model_used": model,
        "tool_calls": executed_tools or None,
        "files": files or None,
    }
