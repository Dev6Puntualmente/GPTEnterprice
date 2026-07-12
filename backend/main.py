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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tools")
def list_tools() -> dict[str, list]:
    return {
        "handlers": sorted(TOOL_HANDLERS.keys()),
        "catalog": TOOL_CATALOG,
    }


@app.post("/chat")
def chat(payload: ChatRequest):
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages no puede estar vacío")

    logger.info(
        "chat request: %s mensajes, vllm=%s",
        len(payload.messages),
        payload.vllm.model if payload.vllm else settings.vllm_model,
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
