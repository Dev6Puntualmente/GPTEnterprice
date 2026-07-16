from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Any

from openai import APIConnectionError, AuthenticationError, BadRequestError, InternalServerError

from config import settings
from services.agent import _endpoint_from_override, stream_agent
from services.agent_types import AgentHandoff, ImmediateResult, StreamHandoff


def _sse_payload(event_type: str, **fields: Any) -> str:
    payload = {"type": event_type, **fields}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _status_event(content: str) -> str:
    return _sse_payload("status", content=content)


def _token_event(content: str) -> str:
    return _sse_payload("token", content=content)


def _error_event(message: str) -> str:
    return _sse_payload("error", message=message)


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
            yield _token_event(token)
    except AuthenticationError:
        yield _error_event(
            "API Key de vLLM inválida o no autorizada. "
            "Debe coincidir con --api-key del servidor (Ajustes → Proveedor de IA)."
        )
        return
    except BadRequestError as error:
        yield _error_event(f"vLLM rechazó la solicitud: {error}")
        return
    except APIConnectionError as error:
        yield _error_event(f"No se pudo conectar al servidor LLM: {error}")
        return
    except InternalServerError as error:
        yield _error_event(_map_llm_exception(error))
        return
    except Exception as error:
        yield _error_event(_map_llm_exception(error))
        return

    yield _sse_payload("done", model_used=model, message="".join(full))


async def stream_sse_events_async(
    messages: list[dict[str, Any]],
    system_prompt: str,
    vllm: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    yield _status_event("Generando respuesta...")
    try:
        events = await asyncio.to_thread(
            lambda: list(stream_sse_events(messages, system_prompt, vllm)),
        )
    except Exception as error:
        yield _error_event(_map_llm_exception(error))
        return
    for event in events:
        yield event


async def _stream_tokens_live(
    messages: list[dict[str, Any]],
    system_prompt: str,
    vllm: dict[str, Any] | None,
) -> AsyncIterator[tuple[str, str]]:
    """Yields (event_sse, raw_token)."""
    loop = asyncio.get_running_loop()
    token_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    def producer() -> None:
        try:
            for token in stream_agent(messages, system_prompt, vllm):
                loop.call_soon_threadsafe(token_queue.put_nowait, ("token", token))
            loop.call_soon_threadsafe(token_queue.put_nowait, ("done", None))
        except Exception as error:
            loop.call_soon_threadsafe(token_queue.put_nowait, ("error", error))

    thread = threading.Thread(target=producer, daemon=True)
    thread.start()

    while True:
        kind, payload = await token_queue.get()
        if kind == "token":
            token = str(payload)
            yield _token_event(token), token
        elif kind == "done":
            break
        elif kind == "error":
            raise payload


async def _iter_tool_phase_events(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None,
    tool_names: list[str] | None,
    vllm: dict[str, Any] | None,
) -> AsyncIterator[str | AgentHandoff]:
    loop = asyncio.get_running_loop()
    progress_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    handoff_box: dict[str, AgentHandoff | Exception | None] = {"value": None}

    def on_status(message: str) -> None:
        loop.call_soon_threadsafe(progress_queue.put_nowait, ("status", message))

    def worker() -> None:
        try:
            from services.tool_orchestration import run_chat_with_tools_handoff

            handoff = run_chat_with_tools_handoff(
                messages,
                system_prompt,
                tools,
                tool_names,
                vllm,
                on_status=on_status,
            )
            handoff_box["value"] = handoff
        except Exception as error:
            handoff_box["value"] = error
        finally:
            loop.call_soon_threadsafe(progress_queue.put_nowait, ("finished", None))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        if handoff_box["value"] is not None and progress_queue.empty():
            break
        try:
            kind, payload = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            continue
        if kind == "status":
            yield _status_event(str(payload))
        elif kind == "finished":
            break

    thread.join(timeout=0.1)
    result = handoff_box["value"]
    if isinstance(result, Exception):
        raise result
    if result is None:
        raise RuntimeError("No se obtuvo resultado del agente con herramientas")
    yield result


def _map_llm_exception(error: Exception) -> str:
    if isinstance(error, AuthenticationError):
        return (
            "API Key de vLLM inválida o no autorizada. "
            "Debe coincidir con --api-key del servidor (Ajustes → Proveedor de IA)."
        )
    if isinstance(error, BadRequestError):
        return f"vLLM rechazó la solicitud: {error}"
    if isinstance(error, APIConnectionError):
        return f"No se pudo conectar al servidor LLM: {error}"
    if isinstance(error, InternalServerError):
        detail = str(error).strip()
        if "tool" in detail.lower() or "parser" in detail.lower():
            return (
                f"Error interno del servidor LLM: {error}. "
                "Si usas tools, configura vLLM con "
                "--enable-auto-tool-choice --tool-call-parser hermes."
            )
        return (
            f"El servidor vLLM respondió con error interno (500). "
            f"{detail or 'Sin detalle.'} "
            "Puede estar reiniciando, sin memoria GPU o con el modelo descargado. "
            "Revisa el estado del servidor en Qontrol / server-monitor."
        )
    return str(error)


async def stream_sse_from_agent_async(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None,
    tool_names: list[str] | None = None,
    vllm: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    _, model, _ = _endpoint_from_override(
        vllm,
        settings.vllm_url,
        settings.vllm_model,
        settings.bearer_api_key,
    )

    try:
        handoff: AgentHandoff | None = None
        async for item in _iter_tool_phase_events(
            messages,
            system_prompt,
            tools,
            tool_names,
            vllm,
        ):
            if isinstance(item, str):
                yield item
            else:
                handoff = item
    except Exception as error:
        yield _error_event(_map_llm_exception(error))
        return

    if handoff is None:
        yield _error_event("No se pudo preparar la respuesta del agente.")
        return

    if isinstance(handoff, ImmediateResult):
        if not handoff.tool_calls:
            yield _status_event("Generando respuesta...")
            full_text = ""
            try:
                async for token_event, token in _stream_tokens_live(
                    messages,
                    system_prompt,
                    vllm,
                ):
                    full_text += token
                    yield token_event
            except Exception as error:
                yield _error_event(_map_llm_exception(error))
                return
            yield _sse_payload(
                "done",
                model_used=handoff.model_used or model,
                message=full_text or handoff.message or "Listo.",
                tool_calls=handoff.tool_calls,
                files=handoff.files,
            )
            return

        final_message = handoff.message or "Listo."
        chunk_size = 4
        for index in range(0, len(final_message), chunk_size):
            yield _token_event(final_message[index : index + chunk_size])
        yield _sse_payload(
            "done",
            model_used=handoff.model_used or model,
            message=final_message,
            tool_calls=handoff.tool_calls,
            files=handoff.files,
        )
        return

    yield _status_event("Redactando respuesta...")

    full_text = ""
    try:
        async for token_event, token in _stream_tokens_live(
            handoff.messages,
            handoff.system_prompt,
            vllm,
        ):
            full_text += token
            yield token_event
    except Exception as error:
        yield _error_event(_map_llm_exception(error))
        return

    yield _sse_payload(
        "done",
        model_used=handoff.model_used or model,
        message=full_text,
        tool_calls=handoff.tool_calls,
        files=handoff.files,
    )


def stream_sse_from_agent(
    messages: list[dict[str, Any]],
    system_prompt: str,
    tools: list[dict[str, Any]] | None,
    tool_names: list[str] | None = None,
    vllm: dict[str, Any] | None = None,
) -> Iterator[str]:
    async def _collect() -> list[str]:
        events: list[str] = []
        async for event in stream_sse_from_agent_async(
            messages,
            system_prompt,
            tools,
            tool_names,
            vllm,
        ):
            events.append(event)
        return events

    for event in asyncio.run(_collect()):
        yield event
