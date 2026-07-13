from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

ProgressCallback = Callable[[str], None]


@dataclass
class ImmediateResult:
    """Respuesta ya generada (sin segunda pasada al LLM)."""

    message: str
    model_used: str = "agent"
    tool_calls: list[dict[str, Any]] | None = None
    files: list[str] | None = None


@dataclass
class StreamHandoff:
    """Datos listos para sintetizar la respuesta final con streaming real."""

    messages: list[dict[str, Any]]
    system_prompt: str
    model_used: str
    tool_calls: list[dict[str, Any]] | None = None
    files: list[str] | None = None


AgentHandoff = ImmediateResult | StreamHandoff
