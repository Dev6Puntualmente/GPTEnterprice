from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from openai import APIConnectionError, AuthenticationError, BadRequestError, NotFoundError
from pydantic import BaseModel

from config import settings
from services.agent import run_agent
from tools.registry import TOOL_CATALOG, TOOL_HANDLERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gptenterprice.agent")

app = FastAPI(title="GPTEnterprice Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORAGE_DIR = Path(settings.storage_dir)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class LlmEndpointOverride(BaseModel):
    base_url: str
    model: str
    api_key: str | None = None


class ChatRequest(BaseModel):
    system_prompt: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    vllm: LlmEndpointOverride | None = None
    stream: bool = True


class ChatResponse(BaseModel):
    message: str
    model_used: str
    tool_calls: list[dict[str, Any]] | None = None
    files: list[str] | None = None
    pending_job: dict[str, Any] | None = None


class EnqueueJobRequest(BaseModel):
    tool: str
    label: str
    args: dict[str, Any]


def _tool_names(payload: ChatRequest) -> list[str]:
    if not payload.tools:
        return []
    names: list[str] = []
    for tool in payload.tools:
        if isinstance(tool, dict):
            fn = tool.get("function") or {}
            name = fn.get("name")
            if name:
                names.append(str(name))
    return names


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "agent-v2-no-loop"}


@app.get("/tools")
def list_tools() -> dict[str, list]:
    return {
        "handlers": sorted(TOOL_HANDLERS.keys()),
        "catalog": TOOL_CATALOG,
    }


@app.get("/jobs")
def jobs(limit: int = 20) -> dict[str, list]:
    from workers.job_runner import list_jobs

    return {"jobs": list_jobs(limit=limit)}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    from workers.job_runner import get_job

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job


@app.post("/jobs")
def enqueue_job(payload: EnqueueJobRequest):
    from workers.job_runner import enqueue_tool_job

    return enqueue_tool_job(payload.tool, payload.label, payload.args)


@app.post("/chat")
def chat(payload: ChatRequest):
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages no puede estar vacío")

    logger.info(
        "chat request: %s mensajes, vllm=%s",
        len(payload.messages),
        payload.vllm.model if payload.vllm else settings.vllm_model,
    )

    from services.intent import detect_heavy_tool_intent
    from services.stream_policy import resolve_effective_stream
    from services.sync_tools import detect_sync_tool_intent, run_sync_tool
    from workers.job_runner import enqueue_tool_job

    tool_names = _tool_names(payload)
    effective_stream = resolve_effective_stream(
        payload.stream,
        payload.messages,
        tool_names,
    )
    if payload.stream and not effective_stream:
        logger.info("stream desactivado: se usarán tools nativas de vLLM")

    sync_intent = detect_sync_tool_intent(payload.messages, tool_names)
    if sync_intent:
        kind = sync_intent.get("type") or sync_intent.get("tool")
        logger.info("sync intent detectado: %s", kind)
        result = run_sync_tool(sync_intent, payload.messages)
        if payload.stream:
            import json as json_lib

            def sync_stream():
                payload_done = {
                    "type": "done",
                    "model_used": "tool",
                    "message": result["message"],
                    "tool_calls": result.get("tool_calls"),
                    "files": result.get("files"),
                }
                yield f"data: {json_lib.dumps({'type': 'token', 'content': result['message']}, ensure_ascii=False)}\n\n"
                yield f"data: {json_lib.dumps(payload_done, ensure_ascii=False)}\n\n"

            return StreamingResponse(sync_stream(), media_type="text/event-stream")
        return ChatResponse(**result)

    intent = detect_heavy_tool_intent(payload.messages, tool_names)
    if intent:
        logger.info("intent detectado en FastAPI: %s %s", intent["tool"], intent["args"])
        job = enqueue_tool_job(intent["tool"], intent["label"], intent["args"])
        start = intent["args"].get("fecha_inicio") or intent["args"].get("hora_inicio")
        end = intent["args"].get("fecha_fin") or intent["args"].get("hora_fin")
        message = (
            f"Perfecto, estoy generando {intent['label']} "
            f"para el periodo {start} → {end}. "
            "Puedes seguir el progreso aquí; te avisaré cuando el Excel esté listo."
        )
        model = payload.vllm.model if payload.vllm else settings.vllm_model
        return ChatResponse(
            message=message,
            model_used=model,
            pending_job={
                "id": job["id"],
                "tool": job["tool"],
                "label": job["label"],
                "status": job["status"],
                "progress": job["progress"],
                "stage": job["stage"],
            },
        )

    # Sync/heavy ya se resolvieron. Stream solo para chat LLM sin tools nativas.
    if effective_stream:
        from services.stream_agent import stream_sse_events

        return StreamingResponse(
            stream_sse_events(
                payload.messages,
                payload.system_prompt,
                payload.vllm.model_dump() if payload.vllm else None,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Sin stream: loop nativo de tools en vLLM solo si está habilitado.
    use_native_tools = settings.vllm_tools_enabled and bool(payload.tools)

    try:
        result = run_agent(
            messages=payload.messages,
            system_prompt=payload.system_prompt,
            tools=payload.tools if use_native_tools else None,
            vllm=payload.vllm.model_dump() if payload.vllm else None,
        )
        return ChatResponse(**result)
    except BadRequestError as error:
        logger.warning("vLLM rejected request: %s", error)
        return JSONResponse(
            status_code=502,
            content={
                "detail": (
                    f"vLLM rechazó la solicitud: {error}. "
                    "Si usas tools, activa VLLM_TOOLS_ENABLED=true y configura "
                    "--enable-auto-tool-choice en el servidor vLLM."
                ),
            },
        )
    except AuthenticationError:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Token inválido o no autorizado para el servidor LLM. Configúralo en Ajustes → Proveedor de IA.",
            },
        )
    except NotFoundError as error:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Modelo no encontrado en vLLM: {error}"},
        )
    except APIConnectionError as error:
        return JSONResponse(
            status_code=502,
            content={"detail": f"No se pudo conectar al servidor LLM: {error}"},
        )
    except Exception as error:
        logger.exception("chat failed")
        return JSONResponse(
            status_code=502,
            content={"detail": f"Error del agente: {error}"},
        )


@app.get("/files/{filename}")
def download_file(filename: str):
    safe_name = Path(filename).name
    filepath = STORAGE_DIR / safe_name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    suffix = filepath.suffix.lower()
    media_type_map = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
    }
    media_type = media_type_map.get(suffix, "application/octet-stream")

    return FileResponse(
        path=filepath,
        filename=safe_name,
        media_type=media_type,
    )
