from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from openai import APIConnectionError, AuthenticationError, BadRequestError

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
