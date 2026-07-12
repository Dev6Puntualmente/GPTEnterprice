from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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

@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "GPTEnterprice Agent v2 listo — rutas: /health /tools /chat /jobs /files/{filename}"
    )


STORAGE_DIR = Path(settings.storage_dir)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    logger.info("→ %s %s", request.method, request.url.path)
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("← %s %s %s (%.0fms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


class LlmEndpointOverride(BaseModel):
    base_url: str
    model: str
    api_key: str | None = None


class ChatRequest(BaseModel):
    system_prompt: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    vllm: LlmEndpointOverride | None = None


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
    return {"status": "ok", "version": "agent-v2-jobs"}


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
    from workers.job_runner import enqueue_tool_job

    intent = detect_heavy_tool_intent(payload.messages, _tool_names(payload))
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

    try:
        result = run_agent(
            messages=payload.messages,
            system_prompt=payload.system_prompt,
            tools=payload.tools,
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
                "detail": "HF_TOKEN inválido o no autorizado para el servidor LLM. Revisa HF_TOKEN en .env",
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
    return FileResponse(
        path=filepath,
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
