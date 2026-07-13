from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

HEAVY_TOOLS = {"reporte_llamadas_excel", "generar_reporte_excel"}

EXCEL_KEYWORDS = ("excel", "xlsx", "exportar", "reporte", "informe", "reprote", "resporte")
CALLS_KEYWORDS = ("llamada", "llamadas", "llmada", "llmadas", "calls")
RRHH_KEYWORDS = ("usuario", "usuarios", "entrada", "rrhh")


def _iso(day: int, month: int, year: int) -> str:
    return date(year, month, day).isoformat()


def _parse_spanish_date(text: str) -> str | None:
    match = re.search(
        r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+(?:de(?:l|\s)?|dl))?\s*(\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    day, month_name, year = match.groups()
    month = SPANISH_MONTHS[month_name.lower()]
    return _iso(int(day), month, int(year))


def _parse_iso_dates(text: str) -> list[str]:
    return re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text)


def _week_range(reference: date | None = None) -> tuple[str, str]:
    today = reference or date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def extract_date_range(text: str) -> tuple[str, str] | None:
    lowered = text.lower()
    current_year = date.today().year

    iso_dates = _parse_iso_dates(text)
    if len(iso_dates) >= 2:
        return iso_dates[0], iso_dates[1]
    if len(iso_dates) == 1:
        return iso_dates[0], iso_dates[0]

    # "9 de julio [de 2026]" — el año es opcional; si falta, se usa el actual
    spanish_dates = []
    for match in re.finditer(
        r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+(?:de(?:l|\s)?|dl)\s*(\d{4}))?",
        text,
        flags=re.IGNORECASE,
    ):
        day, month_name, year = match.groups()
        spanish_dates.append(
            _iso(int(day), SPANISH_MONTHS[month_name.lower()], int(year) if year else current_year)
        )

    if len(spanish_dates) >= 2:
        return spanish_dates[0], spanish_dates[1]
    if len(spanish_dates) == 1:
        return spanish_dates[0], spanish_dates[0]

    compact = re.search(
        r"(?:del\s+)?(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+(?:de(?:l|\s)?|dl)\s*(\d{4}))?",
        lowered,
    )
    if compact:
        start_day, end_day, month_name, year = compact.groups()
        month = SPANISH_MONTHS[month_name.lower()]
        resolved_year = int(year) if year else current_year
        return _iso(int(start_day), month, resolved_year), _iso(int(end_day), month, resolved_year)

    if "esta semana" in lowered or "de esta semana" in lowered:
        return _week_range()

    if re.search(r"\b(?:este|el)\s+mes\b|\bmes\s+actual\b", lowered):
        today = date.today()
        start = date(today.year, today.month, 1)
        if today.month == 12:
            end = date(today.year, 12, 31)
        else:
            end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return start.isoformat(), end.isoformat()

    if re.search(r"\bmes\s+pasado\b|\bmes\s+anterior\b", lowered):
        today = date.today()
        first_this_month = date(today.year, today.month, 1)
        last_prev = first_this_month - timedelta(days=1)
        start = date(last_prev.year, last_prev.month, 1)
        return start.isoformat(), last_prev.isoformat()

    if "hoy" in re.findall(r"\b(hoy)\b", lowered):
        today = date.today().isoformat()
        return today, today

    return None


def _conversation_text(messages: list[dict[str, Any]]) -> str:
    parts = [
        str(message.get("content", ""))
        for message in messages[-8:]
        if message.get("role") in ("user", "USER")
    ]
    return "\n".join(parts)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") in ("user", "USER"):
            return str(message.get("content", ""))
    return ""


def detect_heavy_tool_intent(
    messages: list[dict[str, Any]],
    available_tools: list[str] | None,
) -> dict[str, Any] | None:
    if not available_tools:
        return None

    allowed = set(available_tools) & HEAVY_TOOLS
    if not allowed:
        return None

    recent_text = _conversation_text(messages)
    last_text = _last_user_text(messages)
    recent_lower = recent_text.lower()
    last_lower = last_text.lower()

    wants_excel_now = any(keyword in last_lower for keyword in EXCEL_KEYWORDS)
    wants_calls_now = any(keyword in last_lower for keyword in CALLS_KEYWORDS)
    wants_excel_recent = any(keyword in recent_lower for keyword in EXCEL_KEYWORDS)
    wants_calls_recent = any(keyword in recent_lower for keyword in CALLS_KEYWORDS)

    confirming_dates_only = (
        not wants_excel_now
        and not wants_calls_now
        and extract_date_range(last_text) is not None
        and wants_excel_recent
        and wants_calls_recent
    )

    if "reporte_llamadas_excel" not in allowed:
        return None
    if not ((wants_excel_now and wants_calls_now) or confirming_dates_only):
        return None

    date_range = extract_date_range(recent_text)
    if not date_range:
        return None

    return {
        "tool": "reporte_llamadas_excel",
        "label": "Reporte de llamadas en Excel",
        "args": {
            "fecha_inicio": date_range[0],
            "fecha_fin": date_range[1],
        },
    }
