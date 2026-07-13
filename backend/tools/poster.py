"""
Generación de posters/alertas visuales en SVG.
"""
from __future__ import annotations

import html
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from config import settings

STORAGE_DIR = Path(settings.storage_dir)

THEMES = {
    "alerta": {
        "bg": "#120808",
        "bg2": "#2a0f0f",
        "accent": "#ef4444",
        "accentSoft": "#fca5a5",
        "text": "#fff7f7",
        "subtext": "#fecaca",
        "badge": "ALERTA",
        "icon": "⚠",
    },
    "info": {
        "bg": "#071322",
        "bg2": "#0c2340",
        "accent": "#3b82f6",
        "accentSoft": "#93c5fd",
        "text": "#f8fbff",
        "subtext": "#bfdbfe",
        "badge": "INFORMATIVO",
        "icon": "ℹ",
    },
    "exito": {
        "bg": "#06140c",
        "bg2": "#0d2918",
        "accent": "#22c55e",
        "accentSoft": "#86efac",
        "text": "#f4fff8",
        "subtext": "#bbf7d0",
        "badge": "ÉXITO",
        "icon": "✓",
    },
    "aviso": {
        "bg": "#171005",
        "bg2": "#2d1a05",
        "accent": "#f59e0b",
        "accentSoft": "#fde68a",
        "text": "#fffbeb",
        "subtext": "#fde68a",
        "badge": "AVISO",
        "icon": "◆",
    },
    "neutro": {
        "bg": "#0d0d18",
        "bg2": "#17172a",
        "accent": "#8b5cf6",
        "accentSoft": "#c4b5fd",
        "text": "#faf8ff",
        "subtext": "#ddd6fe",
        "badge": "COMUNICADO",
        "icon": "◈",
    },
}


def _escape(text: str) -> str:
    return html.escape(str(text))


def _wrap_text_lines(text: str, max_chars: int = 28) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:6]


def _decor_circles(accent: str) -> str:
    circles = []
    specs = [(80, 90, 120), (420, 140, 90), (500, 520, 160), (60, 560, 80)]
    for cx, cy, r in specs:
        circles.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{accent}" opacity="0.06"/>'
        )
    return "\n".join(circles)


def generar_poster_alerta(
    titulo: str,
    mensaje: str,
    subtitulo: str | None = None,
    tema: str = "alerta",
    pie_pagina: str | None = None,
) -> dict[str, Any]:
    """Genera un poster visual en SVG listo para ver en el chat o descargar."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    theme_key = tema.lower().strip()
    if theme_key not in THEMES:
        theme_key = "alerta"
    t = THEMES[theme_key]

    titulo_lines = _wrap_text_lines(titulo.upper(), 22)
    mensaje_lines = _wrap_text_lines(mensaje, 34)
    subtitulo_text = _escape(subtitulo) if subtitulo else None
    pie_text = _escape(pie_pagina) if pie_pagina else "GPTEnterprice · Comunicado interno"

    W, H = 600, 820
    card_x, card_y, card_w, card_h = 36, 120, W - 72, H - 200
    title_y = card_y + 56
    title_line_h = 46
    msg_y = title_y + len(titulo_lines) * title_line_h + 28
    msg_line_h = 30

    titulo_svg = "\n".join(
        f'<text x="{W // 2}" y="{title_y + i * title_line_h}" '
        f'text-anchor="middle" dominant-baseline="middle" '
        f'font-family="Segoe UI, Arial Black, sans-serif" font-size="38" '
        f'font-weight="800" letter-spacing="1.5" fill="{t["text"]}">{_escape(line)}</text>'
        for i, line in enumerate(titulo_lines)
    )

    mensaje_svg = "\n".join(
        f'<text x="{W // 2}" y="{msg_y + i * msg_line_h}" '
        f'text-anchor="middle" dominant-baseline="middle" '
        f'font-family="Segoe UI, Arial, sans-serif" font-size="21" '
        f'fill="{t["subtext"]}">{_escape(line)}</text>'
        for i, line in enumerate(mensaje_lines)
    )

    subtitulo_svg = ""
    if subtitulo_text:
        sub_y = msg_y + len(mensaje_lines) * msg_line_h + 28
        subtitulo_svg = (
            f'<text x="{W // 2}" y="{sub_y}" text-anchor="middle" '
            f'font-family="Segoe UI, Arial, sans-serif" font-size="17" font-style="italic" '
            f'fill="{t["accentSoft"]}">{subitulo_text}</text>'
        )

    fecha_str = datetime.now().strftime("%d/%m/%Y · %H:%M")
    icon_size = 54
    icon_y = 62

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{t['bg']}"/>
      <stop offset="100%" stop-color="{t['bg2']}"/>
    </linearGradient>
    <linearGradient id="accentGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{t['accent']}" stop-opacity="0.2"/>
      <stop offset="50%" stop-color="{t['accent']}" stop-opacity="1"/>
      <stop offset="100%" stop-color="{t['accent']}" stop-opacity="0.2"/>
    </linearGradient>
    <filter id="cardShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="12" stdDeviation="18" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <rect width="{W}" height="{H}" rx="24" fill="url(#bgGrad)"/>
  {_decor_circles(t['accent'])}

  <!-- Header strip -->
  <rect x="0" y="0" width="{W}" height="96" fill="{t['accent']}" opacity="0.12"/>
  <rect x="0" y="0" width="{W}" height="5" fill="{t['accent']}"/>

  <!-- Badge -->
  <rect x="{W // 2 - 72}" y="18" width="144" height="30" rx="15" fill="{t['accent']}" opacity="0.22"/>
  <text x="{W // 2}" y="37" text-anchor="middle" dominant-baseline="middle"
        font-family="Segoe UI, Arial, sans-serif" font-size="12" font-weight="700"
        letter-spacing="2.5" fill="{t['accentSoft']}">{t['badge']}</text>

  <!-- Icon circle -->
  <circle cx="{W // 2}" cy="{icon_y}" r="38" fill="{t['accent']}" opacity="0.18"/>
  <circle cx="{W // 2}" cy="{icon_y}" r="30" fill="{t['accent']}" filter="url(#glow)"/>
  <text x="{W // 2}" y="{icon_y + 2}" text-anchor="middle" dominant-baseline="middle"
        font-size="{icon_size}" fill="#ffffff" font-weight="700">{t['icon']}</text>

  <!-- Main card -->
  <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="20"
        fill="rgba(255,255,255,0.04)" stroke="{t['accent']}" stroke-opacity="0.35"
        stroke-width="1.5" filter="url(#cardShadow)"/>

  <rect x="{card_x + 24}" y="{card_y + 18}" width="{card_w - 48}" height="3" rx="1.5" fill="url(#accentGrad)" opacity="0.8"/>

  {titulo_svg}

  <line x1="{card_x + 40}" y1="{msg_y - 18}" x2="{card_x + card_w - 40}" y2="{msg_y - 18}"
        stroke="{t['accent']}" stroke-opacity="0.35" stroke-width="1.5"/>

  {mensaje_svg}
  {subtitulo_svg}

  <!-- Footer -->
  <text x="{W // 2}" y="{H - 42}" text-anchor="middle"
        font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{t['subtext']}" opacity="0.9">
    {pie_text}
  </text>
  <text x="{W - 28}" y="{H - 18}" text-anchor="end"
        font-family="Consolas, monospace" font-size="11" fill="{t['subtext']}" opacity="0.55">
    {fecha_str}
  </text>

  <rect x="0" y="{H - 5}" width="{W}" height="5" fill="{t['accent']}"/>
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
