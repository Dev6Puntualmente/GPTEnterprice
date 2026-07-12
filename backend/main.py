from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config import settings
from services.agent import run_agent
from tools.registry import TOOL_HANDLERS

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


class ChatRequest(BaseModel):
    system_prompt: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None


class ChatResponse(BaseModel):
    message: str
    model_used: str
    tool_calls: list[dict[str, Any]] | None = None
    files: list[str] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tools")
def list_tools() -> dict[str, list[str]]:
    return {"handlers": sorted(TOOL_HANDLERS.keys())}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    if not payload.messages:
        raise HTTPException(status_code=400, detail="messages no puede estar vacío")

    result = run_agent(
        messages=payload.messages,
        system_prompt=payload.system_prompt,
        tools=payload.tools,
    )
    return ChatResponse(**result)


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
