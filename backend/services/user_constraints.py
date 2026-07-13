from __future__ import annotations

import re
from typing import Any

STOPWORDS = {
    "activa",
    "activas",
    "todas",
    "favor",
    "por",
    "listar",
    "listame",
    "dame",
    "muestra",
    "solo",
    "solamente",
    "unicamente",
    "únicamente",
    "nomás",
    "nomas",
    "la",
    "el",
    "de",
    "del",
    "es",
    "una",
    "uno",
    "que",
    "busques",
    "campaña",
    "campana",
    "campañas",
    "campanas",
}


def recent_user_texts(messages: list[dict[str, Any]], limit: int = 4) -> list[str]:
    texts: list[str] = []
    for message in reversed(messages):
        if message.get("role") in ("user", "USER"):
            content = str(message.get("content", "")).strip()
            if content:
                texts.append(content)
            if len(texts) >= limit:
                break
    return list(reversed(texts))


def combined_user_context(messages: list[dict[str, Any]], limit: int = 4) -> str:
    return "\n".join(recent_user_texts(messages, limit=limit))


def wants_exact_match(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(
            r"\bsolo\s+la\s+(?:de\s+)?|\bsolamente\s+la\s+(?:de\s+)?|\bunicamente\s+la\s+(?:de\s+)?|\búnicamente\s+la\s+(?:de\s+)?",
            lowered,
        )
    )


def extract_campaign_filter(text: str) -> tuple[str | None, bool]:
    if not re.search(r"campa[nñ]", text, re.IGNORECASE) and not re.search(
        r"\bsolo\s+la\s+(?:de\s+)?",
        text,
        re.IGNORECASE,
    ):
        return None, False

    patterns = [
        (
            r"\bsolo\s+la\s+(?:de\s+)?(?:la\s+campa[nñ]a\s+)?[\"']?([A-Za-z0-9_\-\s]+?)[\"']?(?:\s|$|,|\.|\?|por)",
            True,
        ),
        (
            r"\bsolamente\s+la\s+(?:de\s+)?(?:la\s+campa[nñ]a\s+)?[\"']?([A-Za-z0-9_\-\s]+?)[\"']?(?:\s|$|,|\.|\?)",
            True,
        ),
        (
            r"\bcampa[nñ]as?\s+(?:de|del|para)\s+[\"']?([A-Za-z0-9_\-\s]+?)[\"']?(?:\s|$|,|\.|\?)",
            False,
        ),
        (
            r"\b(?:filtr(?:ar|a)|busca|buscar)\s+(?:por\s+)?(?:la\s+campa[nñ]a\s+)?[\"']?([A-Za-z0-9_\-\s]+?)[\"']?(?:\s|$|,|\.|\?)",
            False,
        ),
    ]

    for pattern, exact in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        name = match.group(1).strip()
        if name.lower() in STOPWORDS or len(name) < 2:
            continue
        return name, exact or wants_exact_match(text)

    return None, False


def filter_campaign_rows(
    rows: list[dict[str, Any]],
    filter_name: str | None,
    exact: bool = False,
) -> list[dict[str, Any]]:
    if not filter_name:
        return rows

    needle = filter_name.lower().strip()
    if exact:
        filtered = [row for row in rows if str(row.get("name", "")).lower() == needle]
        if filtered:
            return filtered
        return [row for row in rows if str(row.get("name", "")).lower().startswith(needle)]

    return [row for row in rows if needle in str(row.get("name", "")).lower()]


class TranscriptConstraints:
    def __init__(
        self,
        speaker: str | None = None,
        keyword: str | None = None,
        max_segments: int | None = None,
    ) -> None:
        self.speaker = speaker
        self.keyword = keyword
        self.max_segments = max_segments

    @property
    def has_filters(self) -> bool:
        return bool(self.speaker or self.keyword or self.max_segments)


def extract_transcript_constraints(text: str) -> TranscriptConstraints:
    lowered = text.lower()
    speaker: str | None = None

    if re.search(r"\b(agente|asesor|operador|vendedor|ejecutivo)\b", lowered):
        if re.search(r"\bsolo\b|\bsolamente\b|\bunicamente\b|\búnicamente\b|\bnom[aá]s\b", lowered):
            speaker = "Agente"
    if re.search(r"\b(cliente|usuario|contacto|titular)\b", lowered):
        if re.search(r"\bsolo\b|\bsolamente\b|\bunicamente\b|\búnicamente\b|\bnom[aá]s\b", lowered):
            speaker = "Cliente"

    keyword: str | None = None
    keyword_patterns = [
        r"(?:donde|cuando|parte|fragmento|extracto|momento)\s+(?:mencion(?:a|ó|e)|habl(?:a|ó|e)|dice|dijo)\s+(?:sobre|de|del|que)\s+[\"']?(.+?)[\"']?(?:\s|$|\?|\.)",
        r"(?:sobre|acerca de|relacionado con)\s+[\"']?(.+?)[\"']?(?:\s|$|\?|\.)",
        r"(?:busca|buscar|encuentra|extrae|extraer)\s+(?:en la transcripci[oó]n\s+)?[\"']?(.+?)[\"']?(?:\s|$|\?|\.)",
    ]
    for pattern in keyword_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate and candidate.lower() not in STOPWORDS and len(candidate) >= 3:
                keyword = candidate
                break

    max_segments: int | None = None
    limit_match = re.search(
        r"(?:primeras?|últimas?|solo)\s+(\d+)\s+(?:l[ií]neas|oraciones|frases|turnos|intervenciones)",
        lowered,
    )
    if limit_match:
        max_segments = int(limit_match.group(1))

    return TranscriptConstraints(speaker=speaker, keyword=keyword, max_segments=max_segments)


def parse_transcript_segments(transcript: Any) -> list[dict[str, Any]]:
    if transcript is None:
        return []
    if isinstance(transcript, list):
        return [segment for segment in transcript if isinstance(segment, dict)]
    if isinstance(transcript, str):
        stripped = transcript.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            import json

            try:
                parsed = json.loads(stripped)
                return parse_transcript_segments(parsed)
            except json.JSONDecodeError:
                return []
        if stripped:
            return [{"text": stripped, "speaker": None}]
    return []


def apply_transcript_constraints(
    transcript: Any,
    constraints: TranscriptConstraints,
) -> tuple[str, list[str]]:
    segments = parse_transcript_segments(transcript)
    notes: list[str] = []

    if constraints.speaker:
        filtered = [
            segment
            for segment in segments
            if str(segment.get("speaker", "")).lower().startswith(constraints.speaker.lower()[:3])
        ]
        if filtered:
            segments = filtered
            notes.append(f"Filtrado: solo intervenciones de **{constraints.speaker}**.")

    if constraints.keyword:
        needle = constraints.keyword.lower()
        filtered = [
            segment
            for segment in segments
            if needle in str(segment.get("text", "")).lower()
        ]
        if filtered:
            segments = filtered
            notes.append(f"Filtrado: fragmentos que mencionan **{constraints.keyword}**.")
        else:
            notes.append(
                f"No encontré menciones de **{constraints.keyword}**; muestro la transcripción completa."
            )
            segments = parse_transcript_segments(transcript)

    if constraints.max_segments and len(segments) > constraints.max_segments:
        segments = segments[: constraints.max_segments]
        notes.append(f"Mostrando las primeras **{constraints.max_segments}** intervenciones.")

    lines: list[str] = []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        speaker = segment.get("speaker")
        if speaker:
            lines.append(f"**{speaker}:** {text}")
        else:
            lines.append(text)

    return "\n".join(lines), notes


def constraint_summary(text: str, tool: str | None = None) -> str | None:
    parts: list[str] = []

    if tool in (None, "listar_campanas", "buscar_llamadas"):
        campaign, exact = extract_campaign_filter(text)
        if campaign:
            parts.append(f"campaña {'exacta' if exact else 'similar a'} **{campaign}**")

    if tool in (None, "obtener_transcripcion_llamada"):
        transcript = extract_transcript_constraints(text)
        if transcript.speaker:
            parts.append(f"solo **{transcript.speaker}**")
        if transcript.keyword:
            parts.append(f"fragmentos sobre **{transcript.keyword}**")
        if transcript.max_segments:
            parts.append(f"máximo **{transcript.max_segments}** intervenciones")

    if not parts:
        return None
    return "Aplicando filtros: " + ", ".join(parts) + "."
