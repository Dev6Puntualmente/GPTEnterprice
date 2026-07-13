from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from config import settings
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





def run_agent(

    messages: list[dict[str, Any]],

    system_prompt: str,

    tools: list[dict[str, Any]] | None = None,

    vllm: dict[str, Any] | None = None,

) -> dict[str, Any]:

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
            tool_names = [tc.function.name for tc in choice.tool_calls]
            logger.info("LLM solicitó tools: %s", tool_names)

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

