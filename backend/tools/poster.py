"""
🎨 Módulo experimental de generación de posters/alertas visuales.
Genera imágenes SVG que se sirven como archivos estáticos desde /files/.
El SVG resultante puede renderizarse directamente en el chat inline.
"""
from __future__ import annotations

import html
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from config import settings

STORAGE_DIR = Path(settings.storage_dir)

# Paleta de temas de color predefinidos
THEMES = {
    "alerta": {"bg": "#1a0a0a", "accent": "#ef4444", "text": "#fff", "subtext": "#fca5a5", "icon": "⚠️"},
    "info":   {"bg": "#0a1628", "accent": "#3b82f6", "text": "#fff", "subtext": "#93c5fd", "icon": "ℹ️"},
    "exito":  {"bg": "#0a1a0f", "accent": "#22c55e", "text": "#fff", "subtext": "#86efac", "icon": "✅"},
    "aviso":  {"bg": "#1a1200", "accent": "#f59e0b", "text": "#fff", "subtext": "#fde68a", "icon": "🔔"},
    "neutro": {"bg": "#0f0f1a", "accent": "#8b5cf6", "text": "#fff", "subtext": "#c4b5fd", "icon": "📋"},
}


def _escape(text: str) -> str:
    """Escapa texto para uso seguro en SVG/XML."""
    return html.escape(str(text))


def _wrap_text_lines(text: str, max_chars: int = 28) -> list[str]:
    """Parte el texto en líneas respetando palabras."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:5]  # máximo 5 líneas


def generar_poster_alerta(
    titulo: str,
    mensaje: str,
    subtitulo: str | None = None,
    tema: str = "alerta",
    pie_pagina: str | None = None,
) -> dict[str, Any]:
    """
    [EXPERIMENTAL] Genera un poster/imagen de alerta visual en formato SVG.
    Útil para comunicados internos, avisos urgentes o notificaciones visuales.

    El archivo se guarda como SVG y puede verse directamente en el chat.
    """
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Normalizar tema
    theme_key = tema.lower().strip()
    if theme_key not in THEMES:
        theme_key = "alerta"
    t = THEMES[theme_key]

    titulo_lines = _wrap_text_lines(titulo.upper(), 20)
    mensaje_lines = _wrap_text_lines(mensaje, 32)
    subtitulo_text = _escape(subtitulo) if subtitulo else None
    pie_text = _escape(pie_pagina) if pie_pagina else None

    W, H = 480, 640
    title_y_start = 200
    title_line_h = 52
    msg_y_start = title_y_start + len(titulo_lines) * title_line_h + 30
    msg_line_h = 28

    # Generar bloques de texto SVG
    titulo_svg = "\n".join(
        f'<text x="50%" y="{title_y_start + i * title_line_h}" '
        f'dominant-baseline="middle" text-anchor="middle" '
        f'font-family="Arial Black, Impact, sans-serif" font-size="42" '
        f'font-weight="900" fill="{t["text"]}">{_escape(line)}</text>'
        for i, line in enumerate(titulo_lines)
    )

    mensaje_svg = "\n".join(
        f'<text x="50%" y="{msg_y_start + i * msg_line_h}" '
        f'dominant-baseline="middle" text-anchor="middle" '
        f'font-family="Arial, sans-serif" font-size="20" '
        f'fill="{t["subtext"]}">{_escape(line)}</text>'
        for i, line in enumerate(mensaje_lines)
    )

    subtitulo_svg = ""
    if subtitulo_text:
        sub_y = msg_y_start + len(mensaje_lines) * msg_line_h + 24
        subtitulo_svg = (
            f'<text x="50%" y="{sub_y}" dominant-baseline="middle" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="16" font-style="italic" '
            f'fill="{t["accent"]}">{subtitulo_text}</text>'
        )

    pie_svg = ""
    if pie_text:
        pie_svg = (
            f'<text x="50%" y="{H - 32}" dominant-baseline="middle" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="14" fill="{t["subtext"]}88">'
            f'{pie_text}</text>'
        )

    # Línea divisoria accent
    divider_y = title_y_start - 20
    fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{t['bg']};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{t['accent']}22;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="stripe" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{t['accent']};stop-opacity:0" />
      <stop offset="50%" style="stop-color:{t['accent']};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{t['accent']};stop-opacity:0" />
    </linearGradient>
  </defs>

  <!-- Fondo -->
  <rect width="{W}" height="{H}" fill="url(#bg)" rx="16"/>

  <!-- Borde accent -->
  <rect x="2" y="2" width="{W-4}" height="{H-4}" fill="none"
        stroke="{t['accent']}" stroke-width="2" stroke-opacity="0.4" rx="14"/>

  <!-- Líneas decorativas superiores -->
  <rect x="0" y="0" width="{W}" height="6" fill="{t['accent']}" rx="14"/>
  <rect x="0" y="8" width="{W}" height="2" fill="{t['accent']}" opacity="0.3" rx="2"/>

  <!-- Icono / emoji grande -->
  <text x="50%" y="120" dominant-baseline="middle" text-anchor="middle"
        font-size="72">{t['icon']}</text>

  <!-- Línea separadora -->
  <rect x="40" y="{divider_y - 10}" width="{W - 80}" height="2" fill="url(#stripe)" opacity="0.6"/>

  <!-- Título -->
  {titulo_svg}

  <!-- Línea separadora inferior título -->
  <rect x="80" y="{msg_y_start - 16}" width="{W - 160}" height="1.5" fill="{t['accent']}" opacity="0.3"/>

  <!-- Mensaje -->
  {mensaje_svg}

  <!-- Subtítulo -->
  {subtitulo_svg}

  <!-- Pie de página -->
  {pie_svg}

  <!-- Timestamp pequeño -->
  <text x="{W - 12}" y="{H - 14}" text-anchor="end"
        font-family="monospace" font-size="10" fill="{t['subtext']}55">{fecha_str}</text>

  <!-- Línea inferior accent -->
  <rect x="0" y="{H-6}" width="{W}" height="6" fill="{t['accent']}" rx="14"/>
</svg>"""

    filename = f"poster_{uuid.uuid4().hex[:8]}.svg"
    filepath = STORAGE_DIR / filename
    filepath.write_text(svg, encoding="utf-8")

    public_url = f"{settings.public_base_url.rstrip('/')}/files/{filename}"
    return {
        "success": True,
        "archivo": filename,
        "url": public_url,
        "tema": theme_key,
        "mensaje": f"Poster '{titulo}' generado exitosamente.",
    }
