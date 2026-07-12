from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from tools.registry import execute_tool

logger = logging.getLogger("gptenterprice.worker")

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gpt-job")
_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_job(job_id: str, **fields: Any) -> dict[str, Any]:
    with _lock:
        job = _jobs[job_id]
        job.update(fields)
        job["updated_at"] = _utc_now()
        return dict(job)


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda item: item["created_at"], reverse=True)
        return [dict(job) for job in jobs[:limit]]


def _run_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return

    tool = job["tool"]
    args = job["args"]
    label = job["label"]

    logger.info("[job %s] RUNNING %s args=%s", job_id, tool, args)
    _update_job(job_id, status="RUNNING", progress=10, stage="Conectando a la base de datos...")
    time.sleep(0.15)

    try:
        _update_job(job_id, progress=30, stage="Consultando llamadas...")
        time.sleep(0.15)
        raw_result = execute_tool(tool, args)
        parsed = json.loads(raw_result)

        if not parsed.get("success", True) and parsed.get("error"):
            raise RuntimeError(str(parsed["error"]))

        _update_job(job_id, progress=75, stage="Generando archivo Excel...")
        time.sleep(0.15)

        _update_job(
            job_id,
            status="SUCCEEDED",
            progress=100,
            stage="Archivo listo",
            result=parsed,
            finished_at=_utc_now(),
        )
        logger.info("[job %s] SUCCEEDED %s", job_id, parsed.get("archivo") or label)
    except Exception as error:
        logger.exception("[job %s] FAILED", job_id)
        _update_job(
            job_id,
            status="FAILED",
            progress=100,
            stage="Error al generar archivo",
            error=str(error),
            finished_at=_utc_now(),
        )


def enqueue_tool_job(tool: str, label: str, args: dict[str, Any]) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "tool": tool,
        "label": label,
        "args": args,
        "status": "PENDING",
        "progress": 0,
        "stage": "En cola...",
        "result": None,
        "error": None,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "started_at": None,
        "finished_at": None,
    }

    with _lock:
        _jobs[job_id] = job

    logger.info("[job %s] QUEUED %s", job_id, tool)

    def _start() -> None:
        _update_job(job_id, status="RUNNING", started_at=_utc_now(), stage="Iniciando worker...")
        _run_job(job_id)

    _executor.submit(_start)
    return dict(job)
