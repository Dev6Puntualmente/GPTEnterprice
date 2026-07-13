from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

from openai import APIConnectionError, AuthenticationError, BadRequestError, InternalServerError

from config import settings
from services.agent import _build_client, _endpoint_from_override


def stream_agent(
    messages: list[dict[str, Any]],
    system_prompt: str,
    vllm: dict[str, Any] | None = None,
) -> Iterator[str]:
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


def stream_sse_events(
    messages: list[dict[str, Any]],
    system_prompt: str,
    vllm: dict[str, Any] | None = None,
) -> Iterator[str]:
    _, model, _ = _endpoint_from_override(
        vllm,
        settings.vllm_url,
        settings.vllm_model,
        settings.bearer_api_key,
    )
    full: list[str] = []
    try:
        for token in stream_agent(messages, system_prompt, vllm):
            full.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
    except AuthenticationError:
        message = (
            "API Key de vLLM inválida o no autorizada. "
            "Debe coincidir con --api-key del servidor (Ajustes → Proveedor de IA)."
        )
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return
    except BadRequestError as error:
        message = f"vLLM rechazó la solicitud: {error}"
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return
    except APIConnectionError as error:
        message = f"No se pudo conectar al servidor LLM: {error}"
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return

    yield f"data: {json.dumps({'type': 'done', 'model_used': model, 'message': ''.join(full)}, ensure_ascii=False)}\n\n"


async def stream_sse_events_async(
    messages: list[dict[str, Any]],
    system_prompt: str,
    vllm: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    yield f"data: {json.dumps({'type': 'status', 'content': 'Generando respuesta...'}, ensure_ascii=False)}\n\n"
    events = await asyncio.to_thread(
        lambda: list(stream_sse_events(messages, system_prompt, vllm)),
    )
    for event in events:
        yield event


def _chunk_text(text: str, size: int = 16) -> list[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


def stream_sse_from_agent(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None,
    tool_names: list[str] | None = None,
    vllm: dict[str, Any] | None = None,
) -> Iterator[str]:
    """Ejecuta chat con tools (nativas o fallback) y emite la respuesta final como SSE."""
    from services.tool_orchestration import run_chat_with_tools

    _, model, _ = _endpoint_from_override(
        vllm,
        settings.vllm_url,
        settings.vllm_model,
        settings.bearer_api_key,
    )

    yield f"data: {json.dumps({'type': 'status', 'content': 'Analizando y consultando datos...'}, ensure_ascii=False)}\n\n"

    try:
        result = run_chat_with_tools(
            messages=messages,
            system_prompt=system_prompt,
            tools=tools,
            tool_names=tool_names,
            vllm=vllm,
        )
    except AuthenticationError:
        message = (
            "API Key de vLLM inválida o no autorizada. "
            "Debe coincidir con --api-key del servidor (Ajustes → Proveedor de IA)."
        )
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return
    except BadRequestError as error:
        message = f"vLLM rechazó la solicitud: {error}"
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return
    except APIConnectionError as error:
        message = f"No se pudo conectar al servidor LLM: {error}"
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return
    except InternalServerError as error:
        message = (
            f"El servidor LLM no soporta tool-calling en esta configuración: {error}. "
            "En vLLM usa --enable-auto-tool-choice --tool-call-parser hermes."
        )
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return

    final_message = result.get("message") or ""
    for chunk in _chunk_text(final_message, 18):
        yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

    yield f"data: {json.dumps({
        'type': 'done',
        'model_used': result.get('model_used') or model,
        'message': final_message,
        'tool_calls': result.get('tool_calls'),
        'files': result.get('files'),
    }, ensure_ascii=False)}\n\n"


async def stream_sse_from_agent_async(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None,
    tool_names: list[str] | None = None,
    vllm: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    from services.tool_orchestration import run_chat_with_tools

    _, model, _ = _endpoint_from_override(
        vllm,
        settings.vllm_url,
        settings.vllm_model,
        settings.bearer_api_key,
    )

    yield f"data: {json.dumps({'type': 'status', 'content': 'Analizando y consultando datos...'}, ensure_ascii=False)}\n\n"

    try:
        result = await asyncio.to_thread(
            run_chat_with_tools,
            messages,
            system_prompt,
            tools,
            tool_names,
            vllm,
        )
    except AuthenticationError:
        message = (
            "API Key de vLLM inválida o no autorizada. "
            "Debe coincidir con --api-key del servidor (Ajustes → Proveedor de IA)."
        )
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return
    except BadRequestError as error:
        message = f"vLLM rechazó la solicitud: {error}"
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return
    except APIConnectionError as error:
        message = f"No se pudo conectar al servidor LLM: {error}"
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return
    except InternalServerError as error:
        message = (
            f"El servidor LLM no soporta tool-calling en esta configuración: {error}. "
            "En vLLM usa --enable-auto-tool-choice --tool-call-parser hermes."
        )
        yield f"data: {json.dumps({'type': 'error', 'message': message}, ensure_ascii=False)}\n\n"
        return

    final_message = result.get("message") or ""
    for chunk in _chunk_text(final_message, 18):
        yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

    yield f"data: {json.dumps({
        'type': 'done',
        'model_used': result.get('model_used') or model,
        'message': final_message,
        'tool_calls': result.get('tool_calls'),
        'files': result.get('files'),
    }, ensure_ascii=False)}\n\n"
