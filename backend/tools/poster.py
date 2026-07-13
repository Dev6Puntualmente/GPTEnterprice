"""
Generación de posters/comunicados visuales en PNG (Pillow).
Qwen rellena estructura y estilo vía tool-calling; este módulo renderiza la plantilla.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from config import settings

STORAGE_DIR = Path(settings.storage_dir)

THEMES: dict[str, dict[str, str]] = {
    "alerta": {
        "bg": "#120808",
        "bg2": "#2a0f0f",
        "accent": "#ef4444",
        "accent_soft": "#fca5a5",
        "text": "#fff7f7",
        "subtext": "#fecaca",
        "badge": "ALERTA",
    },
    "info": {
        "bg": "#071322",
        "bg2": "#0c2340",
        "accent": "#3b82f6",
        "accent_soft": "#93c5fd",
        "text": "#f8fbff",
        "subtext": "#bfdbfe",
        "badge": "INFORMATIVO",
    },
    "exito": {
        "bg": "#06140c",
        "bg2": "#0d2918",
        "accent": "#22c55e",
        "accent_soft": "#86efac",
        "text": "#f4fff8",
        "subtext": "#bbf7d0",
        "badge": "ÉXITO",
    },
    "aviso": {
        "bg": "#171005",
        "bg2": "#2d1a05",
        "accent": "#f59e0b",
        "accent_soft": "#fde68a",
        "text": "#fffbeb",
        "subtext": "#fde68a",
        "badge": "AVISO",
    },
    "neutro": {
        "bg": "#0d0d18",
        "bg2": "#17172a",
        "accent": "#8b5cf6",
        "accent_soft": "#c4b5fd",
        "text": "#faf8ff",
        "subtext": "#ddd6fe",
        "badge": "COMUNICADO",
    },
}

COLOR_SCHEME_TO_THEME = {
    "corporativo_azul": "info",
    "ecologico_verde": "exito",
    "alerta_rojo": "alerta",
    "minimalista_oscuro": "neutro",
    "aviso_naranja": "aviso",
}

SECTION_ICON_LABELS = {
    "reciclaje": "R",
    "grafico_barras": "G",
    "usuario": "U",
    "alerta": "!",
    "agua": "A",
    "info": "i",
    "exito": "+",
}

FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)
FONT_REGULAR_CANDIDATES = (
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)
FONT_MONO_CANDIDATES = (
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/cour.ttf"),
)


def _parse_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _hex_color(value: str | None, fallback: str) -> tuple[int, int, int]:
    raw = (value or fallback).strip()
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", raw):
        raw = fallback if fallback.startswith("#") else f"#{fallback}"
    return int(raw[1:3], 16), int(raw[3:5], 16), int(raw[5:7], 16)


def _load_font(candidates: tuple[Path, ...], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = font.getbbox(candidate)
        width = bbox[2] - bbox[0]
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]


def _vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return image


def _resolve_theme_key(tema: str | None, color_esquema: str | None) -> str:
    if color_esquema:
        mapped = COLOR_SCHEME_TO_THEME.get(color_esquema.strip().lower())
        if mapped:
            return mapped
    theme_key = (tema or "alerta").lower().strip()
    if theme_key in COLOR_SCHEME_TO_THEME:
        return COLOR_SCHEME_TO_THEME[theme_key]
    if theme_key not in THEMES:
        return "alerta"
    return theme_key


def _build_style(
    *,
    tema: str | None,
    color_esquema: str | None,
    color_fondo: str | None = None,
    color_fondo_secundario: str | None = None,
    color_texto: str | None = None,
    color_texto_secundario: str | None = None,
    color_acento: str | None = None,
    color_badge: str | None = None,
    ancho: Any = 600,
    alto: Any | None = None,
    margen: Any = 36,
    tamano_fuente_titulo: Any | None = None,
    tamano_fuente_cuerpo: Any | None = None,
    tamano_fuente_subtitulo: Any | None = None,
    tamano_fuente_pie: Any | None = None,
    badge_texto: str | None = None,
    num_secciones: int = 1,
) -> dict[str, Any]:
    theme_key = _resolve_theme_key(tema, color_esquema)
    preset = THEMES[theme_key]

    width = _parse_int(ancho, 600, minimum=400, maximum=1400)
    scale = width / 600
    margin = _parse_int(margen, int(36 * scale), minimum=16, maximum=120)
    base_height = int(820 * scale)
    extra_height = max(0, num_secciones - 1) * int(110 * scale)
    auto_height = base_height + extra_height
    height = _parse_int(alto, auto_height, minimum=500, maximum=2200) if alto is not None else auto_height

    title_size = _parse_int(
        tamano_fuente_titulo,
        int(38 * scale),
        minimum=18,
        maximum=96,
    )
    body_size = _parse_int(
        tamano_fuente_cuerpo,
        int(15 * scale),
        minimum=11,
        maximum=48,
    )
    subtitle_size = _parse_int(
        tamano_fuente_subtitulo,
        int(16 * scale),
        minimum=11,
        maximum=48,
    )
    footer_size = _parse_int(
        tamano_fuente_pie,
        int(13 * scale),
        minimum=9,
        maximum=32,
    )

    return {
        "theme_key": theme_key,
        "width": width,
        "height": height,
        "margin": margin,
        "title_size": title_size,
        "body_size": body_size,
        "subtitle_size": subtitle_size,
        "footer_size": footer_size,
        "bg": _hex_color(color_fondo, preset["bg"]),
        "bg2": _hex_color(color_fondo_secundario or color_fondo, preset["bg2"]),
        "text": _hex_color(color_texto, preset["text"]),
        "subtext": _hex_color(color_texto_secundario or color_texto, preset["subtext"]),
        "accent": _hex_color(color_acento, preset["accent"]),
        "accent_soft": _hex_color(color_badge or color_acento, preset["accent_soft"]),
        "badge": (badge_texto or preset["badge"]).upper()[:24],
    }


def _normalize_sections(
    secciones: list[dict[str, Any]] | None,
    secciones_informativas: list[dict[str, Any]] | None,
    mensaje: str | None,
) -> list[dict[str, str]]:
    raw = secciones_informativas or secciones or []
    normalized: list[dict[str, str]] = []
    for item in raw[:3]:
        if not isinstance(item, dict):
            continue
        subtitulo = (
            item.get("subtitulo")
            or item.get("titulo_seccion")
            or item.get("title")
            or ""
        )
        contenido = (
            item.get("contenido_texto")
            or item.get("contenido")
            or item.get("texto")
            or item.get("mensaje")
            or ""
        )
        if not str(subtitulo).strip() and not str(contenido).strip():
            continue
        icon_key = str(item.get("icono_svg_sugerido") or item.get("icono") or "").lower()
        normalized.append(
            {
                "subtitulo": str(subtitulo).strip() or "Detalle",
                "contenido": str(contenido).strip(),
                "icono": SECTION_ICON_LABELS.get(icon_key, subtitulo.strip()[:1].upper() or "•"),
            }
        )
    if not normalized and mensaje and mensaje.strip():
        normalized.append(
            {
                "subtitulo": "Mensaje",
                "contenido": mensaje.strip(),
                "icono": "M",
            }
        )
    return normalized


def _draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    y_start: int,
    line_height: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    canvas_width: int,
) -> int:
    y = y_start
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (canvas_width - text_w) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _render_poster_png(
    *,
    style: dict[str, Any],
    title: str,
    sections: list[dict[str, str]],
    subtitulo: str | None,
    pie_pagina: str,
) -> Image.Image:
    width = style["width"]
    height = style["height"]
    margin = style["margin"]
    accent = style["accent"]
    text_color = style["text"]
    subtext = style["subtext"]

    image = _vertical_gradient((width, height), style["bg"], style["bg2"]).convert("RGBA")
    draw = ImageDraw.Draw(image)

    header_h = int(96 * (width / 600))
    draw.rectangle([(0, 0), (width, header_h)], fill=(*accent, 30))
    draw.rectangle([(0, 0), (width, max(4, int(5 * width / 600)))], fill=accent)

    badge_font = _load_font(FONT_REGULAR_CANDIDATES, max(10, int(12 * width / 600)))
    badge_w = min(width - margin * 2, 220)
    badge_x = (width - badge_w) // 2
    badge_y = int(18 * width / 600)
    badge_h = int(30 * width / 600)
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=badge_h // 2,
        fill=(*accent, 55),
    )
    badge_bbox = draw.textbbox((0, 0), style["badge"], font=badge_font)
    badge_text_w = badge_bbox[2] - badge_bbox[0]
    draw.text(
        ((width - badge_text_w) // 2, badge_y + 6),
        style["badge"],
        font=badge_font,
        fill=style["accent_soft"],
    )

    icon_y = int(62 * width / 600)
    icon_r = int(30 * width / 600)
    draw.ellipse(
        [(width // 2 - icon_r - 8, icon_y - icon_r - 8), (width // 2 + icon_r + 8, icon_y + icon_r + 8)],
        fill=(*accent, 45),
    )
    draw.ellipse(
        [(width // 2 - icon_r, icon_y - icon_r), (width // 2 + icon_r, icon_y + icon_r)],
        fill=accent,
    )
    icon_font = _load_font(FONT_CANDIDATES, int(28 * width / 600))
    icon_char = "!" if style["theme_key"] == "alerta" else "i"
    icon_bbox = draw.textbbox((0, 0), icon_char, font=icon_font)
    draw.text(
        (width // 2 - (icon_bbox[2] - icon_bbox[0]) // 2, icon_y - (icon_bbox[3] - icon_bbox[1]) // 2 - 2),
        icon_char,
        font=icon_font,
        fill=(255, 255, 255),
    )

    card_x = margin
    card_y = int(120 * width / 600)
    card_w = width - margin * 2
    card_h = height - card_y - int(90 * width / 600)
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        radius=int(20 * width / 600),
        fill=(255, 255, 255, 10),
        outline=(*accent, 90),
        width=max(1, int(1.5 * width / 600)),
    )

    title_font = _load_font(FONT_CANDIDATES, style["title_size"])
    body_font = _load_font(FONT_REGULAR_CANDIDATES, style["body_size"])
    subtitle_font = _load_font(FONT_REGULAR_CANDIDATES, style["subtitle_size"])
    footer_font = _load_font(FONT_REGULAR_CANDIDATES, style["footer_size"])
    mono_font = _load_font(FONT_MONO_CANDIDATES, max(9, style["footer_size"] - 2))

    title_lines = _wrap_text(title.upper(), title_font, card_w - 48, 4)
    title_y = card_y + int(36 * width / 600)
    title_line_h = int(style["title_size"] * 1.2)
    next_y = _draw_centered_lines(
        draw,
        title_lines,
        y_start=title_y,
        line_height=title_line_h,
        font=title_font,
        fill=text_color,
        canvas_width=width,
    )

    if subtitulo:
        sub_bbox = draw.textbbox((0, 0), subtitulo, font=subtitle_font)
        draw.text(
            ((width - (sub_bbox[2] - sub_bbox[0])) // 2, next_y + 8),
            subtitulo,
            font=subtitle_font,
            fill=style["accent_soft"],
        )
        next_y += int(style["subtitle_size"] * 1.6)

    section_y = next_y + int(24 * width / 600)
    inner_x = card_x + int(16 * width / 600)
    inner_w = card_w - int(32 * width / 600)

    for section in sections:
        content_lines = _wrap_text(section["contenido"], body_font, inner_w - 70, 3)
        box_h = int(78 * width / 600) + max(0, len(content_lines) - 1) * int(22 * width / 600)
        draw.rounded_rectangle(
            [(inner_x, section_y), (inner_x + inner_w, section_y + box_h)],
            radius=int(14 * width / 600),
            fill=(255, 255, 255, 12),
            outline=(*accent, 60),
            width=1,
        )

        icon_r = int(16 * width / 600)
        icon_cx = inner_x + int(26 * width / 600)
        icon_cy = section_y + int(28 * width / 600)
        draw.ellipse(
            [(icon_cx - icon_r, icon_cy - icon_r), (icon_cx + icon_r, icon_cy + icon_r)],
            fill=(*accent, 65),
        )
        icon_font_small = _load_font(FONT_CANDIDATES, int(14 * width / 600))
        icon_label = section["icono"][:1]
        icon_bbox = draw.textbbox((0, 0), icon_label, font=icon_font_small)
        draw.text(
            (icon_cx - (icon_bbox[2] - icon_bbox[0]) // 2, icon_cy - (icon_bbox[3] - icon_bbox[1]) // 2 - 1),
            icon_label,
            font=icon_font_small,
            fill=(255, 255, 255),
        )

        text_x = inner_x + int(52 * width / 600)
        draw.text((text_x, section_y + 12), section["subtitulo"], font=subtitle_font, fill=text_color)
        line_y = section_y + int(36 * width / 600)
        for line in content_lines:
            draw.text((text_x, line_y), line, font=body_font, fill=subtext)
            line_y += int(22 * width / 600)
        section_y += box_h + int(14 * width / 600)

    footer_y = height - int(42 * width / 600)
    footer_bbox = draw.textbbox((0, 0), pie_pagina, font=footer_font)
    draw.text(
        ((width - (footer_bbox[2] - footer_bbox[0])) // 2, footer_y),
        pie_pagina,
        font=footer_font,
        fill=subtext,
    )
    fecha_str = datetime.now().strftime("%d/%m/%Y · %H:%M")
    draw.text((width - margin, height - int(18 * width / 600)), fecha_str, font=mono_font, fill=subtext)
    draw.rectangle([(0, height - max(4, int(5 * width / 600))), (width, height)], fill=accent)

    return image.convert("RGB")


def generar_poster_alerta(
    titulo: str | None = None,
    mensaje: str | None = None,
    subtitulo: str | None = None,
    tema: str = "alerta",
    pie_pagina: str | None = None,
    *,
    titulo_principal: str | None = None,
    color_esquema: str | None = None,
    secciones: list[dict[str, Any]] | None = None,
    secciones_informativas: list[dict[str, Any]] | None = None,
    color_fondo: str | None = None,
    color_fondo_secundario: str | None = None,
    color_texto: str | None = None,
    color_texto_secundario: str | None = None,
    color_acento: str | None = None,
    color_badge: str | None = None,
    ancho: int | str | float | None = None,
    alto: int | str | float | None = None,
    margen: int | str | float | None = None,
    tamano_fuente_titulo: int | str | float | None = None,
    tamano_fuente_cuerpo: int | str | float | None = None,
    tamano_fuente_subtitulo: int | str | float | None = None,
    tamano_fuente_pie: int | str | float | None = None,
    badge_texto: str | None = None,
) -> dict[str, Any]:
    """Genera un poster PNG parametrizable. Qwen puede elegir colores, tamaños y secciones."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    resolved_title = (titulo_principal or titulo or "Aviso importante").strip()
    sections = _normalize_sections(secciones, secciones_informativas, mensaje)
    if not sections:
        return {
            "success": False,
            "mensaje": "Indica al menos un mensaje o secciones_informativas para el poster.",
        }

    style = _build_style(
        tema=tema,
        color_esquema=color_esquema,
        color_fondo=color_fondo,
        color_fondo_secundario=color_fondo_secundario,
        color_texto=color_texto,
        color_texto_secundario=color_texto_secundario,
        color_acento=color_acento,
        color_badge=color_badge,
        ancho=ancho or 600,
        alto=alto,
        margen=margen or 36,
        tamano_fuente_titulo=tamano_fuente_titulo,
        tamano_fuente_cuerpo=tamano_fuente_cuerpo,
        tamano_fuente_subtitulo=tamano_fuente_subtitulo,
        tamano_fuente_pie=tamano_fuente_pie,
        badge_texto=badge_texto,
        num_secciones=len(sections),
    )

    pie_text = pie_pagina or "GPTEnterprice · Comunicado interno"
    image = _render_poster_png(
        style=style,
        title=resolved_title,
        sections=sections,
        subtitulo=subtitulo.strip() if subtitulo else None,
        pie_pagina=pie_text,
    )

    filename = f"poster_{uuid.uuid4().hex[:8]}.png"
    filepath = STORAGE_DIR / filename
    image.save(filepath, format="PNG", optimize=True)

    public_url = f"{settings.public_base_url.rstrip('/')}/files/{filename}"
    return {
        "success": True,
        "archivo": filename,
        "formato": "png",
        "url": public_url,
        "ancho": style["width"],
        "alto": style["height"],
        "tema": style["theme_key"],
        "color_esquema": color_esquema or style["theme_key"],
        "estilo": {
            "color_fondo": color_fondo,
            "color_fondo_secundario": color_fondo_secundario,
            "color_texto": color_texto,
            "color_texto_secundario": color_texto_secundario,
            "color_acento": color_acento,
            "tamano_fuente_titulo": style["title_size"],
            "tamano_fuente_cuerpo": style["body_size"],
        },
        "secciones": len(sections),
        "mensaje": f"Poster PNG '{resolved_title}' ({style['width']}×{style['height']}) generado.",
    }


def generar_estructura_poster(**kwargs: Any) -> dict[str, Any]:
    """Alias con el nombre sugerido por el esquema de tool-calling estructurado."""
    return generar_poster_alerta(**kwargs)
