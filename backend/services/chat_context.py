from __future__ import annotations

from typing import Any


def trim_messages_for_agent(
    messages: list[dict[str, Any]],
    per_role: int = 3,
) -> list[dict[str, Any]]:
    """Conserva los últimos N mensajes de usuario y N del asistente (sin tool)."""
    users = 0
    assistants = 0
    kept: list[dict[str, Any]] = []

    for message in reversed(messages):
        role = str(message.get("role", "")).lower()
        if role == "user":
            if users >= per_role:
                continue
            users += 1
        elif role == "assistant":
            if assistants >= per_role:
                continue
            assistants += 1
        else:
            continue
        kept.insert(0, message)

    return kept
