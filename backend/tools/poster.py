"""
Generación de posters/comunicados visuales en PNG (Pillow).
Layout medido + contraste automático para que el texto siempre sea legible.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from config import settings
from utils.file_urls import public_file_url

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
    "agua": "H2O",
    "info": "i",
    "exito": "+",
}


def _draw_section_icon(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    radius: int,
    label: str,
    accent: tuple[int, int, int],
    font: ImageFont.ImageFont,
) -> None:
    draw.ellipse([(x - radius, y - radius), (x + radius, y + radius)], fill=accent)
    text = label[:3]
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x - tw // 2, y - th // 2 - 1), text, font=font, fill=(255, 255, 255))

FONT_BOLD = (
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
)
FONT_REGULAR = (
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)
FONT_MONO = (
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


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (channel / 255.0 for channel in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _blend(a: tuple[int, int, int], b: tuple[int, int, int], ratio: float) -> tuple[int, int, int]:
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(a[i] * (1 - ratio) + b[i] * ratio) for i in range(3))


def _pick_text_on(bg: tuple[int, int, int], preferred: tuple[int, int, int], fallback_light: tuple[int, int, int], fallback_dark: tuple[int, int, int]) -> tuple[int, int, int]:
    if _luminance(preferred) > 0.55 and _luminance(bg) > 0.45:
        return fallback_dark
    if _luminance(preferred) < 0.45 and _luminance(bg) < 0.35:
        return fallback_light
    return preferred


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
        if (bbox[2] - bbox[0]) <= max_width or not current:
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


def _draw_glow_circles(draw: ImageDraw.ImageDraw, width: int, height: int, accent: tuple[int, int, int]) -> None:
    specs = [
        (int(width * 0.12), int(height * 0.08), int(width * 0.22)),
        (int(width * 0.88), int(height * 0.18), int(width * 0.16)),
        (int(width * 0.78), int(height * 0.82), int(width * 0.28)),
    ]
    for cx, cy, radius in specs:
        draw.ellipse(
            [(cx - radius, cy - radius), (cx + radius, cy + radius)],
            fill=_blend(accent, (0, 0, 0), 0.88),
        )


def _resolve_theme_key(tema: str | None, color_esquema: str | None) -> str:
    if color_esquema:
        mapped = COLOR_SCHEME_TO_THEME.get(color_esquema.strip().lower())
        if mapped:
            return mapped
    theme_key = (tema or "alerta").lower().strip()
    if theme_key in COLOR_SCHEME_TO_THEME:
        return COLOR_SCHEME_TO_THEME[theme_key]
    return theme_key if theme_key in THEMES else "alerta"


def _normalize_sections(
    secciones: list[dict[str, Any]] | None,
    secciones_informativas: list[dict[str, Any]] | None,
    mensaje: str | None,
) -> list[dict[str, str]]:
    raw = secciones_informativas or secciones or []
    normalized: list[dict[str, str]] = []
    for item in raw[:4]:
        if not isinstance(item, dict):
            continue
        subtitulo = item.get("subtitulo") or item.get("titulo_seccion") or item.get("title") or ""
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
                "icono": SECTION_ICON_LABELS.get(icon_key, "•"),
            }
        )
    if not normalized and mensaje and mensaje.strip():
        normalized.append({"subtitulo": "Mensaje", "contenido": mensaje.strip(), "icono": "•"})
    return normalized


def _measure_section_height(
    section: dict[str, str],
    *,
    inner_w: int,
    body_font: ImageFont.ImageFont,
    heading_font: ImageFont.ImageFont,
    scale: float,
) -> int:
    content_lines = _wrap_text(section["contenido"], body_font, inner_w - int(56 * scale), 4)
    base = int(72 * scale)
    return base + max(0, len(content_lines) - 1) * int(24 * scale)


def _compute_layout(
    *,
    width: int,
    margin: int,
    title: str,
    sections: list[dict[str, str]],
    subtitulo: str | None,
    title_size: int,
    body_size: int,
    subtitle_size: int,
    requested_height: int | None,
) -> dict[str, Any]:
    scale = width / 600
    title_font = _load_font(FONT_BOLD, title_size)
    body_font = _load_font(FONT_REGULAR, body_size)
    heading_font = _load_font(FONT_BOLD, subtitle_size)
    card_w = width - margin * 2
    inner_w = card_w - int(32 * scale)

    title_lines = _wrap_text(title.upper(), title_font, card_w - int(40 * scale), 3)
    title_block = int(28 * scale) + len(title_lines) * int(title_size * 1.15)
    subtitle_block = int(subtitle_size * 1.8) if subtitulo else 0
    header_block = int(118 * scale) + title_block + subtitle_block

    section_heights = [
        _measure_section_height(section, inner_w=inner_w, body_font=body_font, heading_font=heading_font, scale=scale)
        for section in sections
    ]
    gap = int(14 * scale)
    sections_block = sum(section_heights) + gap * max(0, len(sections) - 1) + int(24 * scale)
    footer_block = int(72 * scale)
    needed = header_block + sections_block + footer_block + margin

    if requested_height is None or requested_height < needed:
        height = min(2400, max(needed, int(640 * scale)))
    else:
        height = min(2400, requested_height)

    return {
        "height": height,
        "title_lines": title_lines,
        "section_heights": section_heights,
        "scale": scale,
        "title_font": title_font,
        "body_font": body_font,
        "heading_font": heading_font,
        "card_w": card_w,
        "inner_w": inner_w,
    }


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
    title: str = "",
    sections: list[dict[str, str]] | None = None,
    subtitulo: str | None = None,
) -> dict[str, Any]:
    theme_key = _resolve_theme_key(tema, color_esquema)
    preset = THEMES[theme_key]
    width = _parse_int(ancho, 600, minimum=400, maximum=1400)
    scale = width / 600
    margin = _parse_int(margen, int(36 * scale), minimum=20, maximum=120)

    title_size = _parse_int(tamano_fuente_titulo, int(42 * scale), minimum=22, maximum=96)
    if title_size < int(34 * scale) and width >= 640:
        title_size = int(40 * scale)
    body_size = _parse_int(tamano_fuente_cuerpo, int(16 * scale), minimum=12, maximum=40)
    subtitle_size = _parse_int(tamano_fuente_subtitulo, int(18 * scale), minimum=13, maximum=40)
    footer_size = _parse_int(tamano_fuente_pie, int(12 * scale), minimum=10, maximum=24)

    requested_height = _parse_int(alto, 0, minimum=0, maximum=2400) if alto is not None else None
    if requested_height == 0:
        requested_height = None

    layout = _compute_layout(
        width=width,
        margin=margin,
        title=title,
        sections=sections or [],
        subtitulo=subtitulo,
        title_size=title_size,
        body_size=body_size,
        subtitle_size=subtitle_size,
        requested_height=requested_height,
    )

    bg = _hex_color(color_fondo, preset["bg"])
    bg2 = _hex_color(color_fondo_secundario or color_fondo, preset["bg2"])
    accent = _hex_color(color_acento, preset["accent"])
    text = _hex_color(color_texto, preset["text"])
    subtext = _hex_color(color_texto_secundario or color_texto, preset["subtext"])
    section_bg = _blend(accent, bg, 0.82)
    section_heading = _pick_text_on(section_bg, accent, (255, 255, 255), (20, 30, 20))
    section_body = _pick_text_on(section_bg, subtext, (240, 250, 240), (30, 45, 30))
    title_color = _pick_text_on(bg, text, (255, 255, 255), (15, 25, 15))
    subtitle_color = _pick_text_on(bg, _hex_color(color_badge, preset["accent_soft"]), (255, 255, 255), (40, 60, 40))

    return {
        "theme_key": theme_key,
        "width": width,
        "height": layout["height"],
        "margin": margin,
        "title_size": title_size,
        "body_size": body_size,
        "subtitle_size": subtitle_size,
        "footer_size": footer_size,
        "bg": bg,
        "bg2": bg2,
        "text": title_color,
        "subtext": subtitle_color,
        "accent": accent,
        "accent_soft": _hex_color(color_badge, preset["accent_soft"]),
        "section_bg": section_bg,
        "section_heading": section_heading,
        "section_body": section_body,
        "badge": (badge_texto or preset["badge"]).upper()[:24],
        "layout": layout,
        "alto_ajustado": requested_height is not None and requested_height < layout["height"],
    }


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
    layout = style["layout"]
    scale = layout["scale"]

    image = _vertical_gradient((width, height), style["bg"], style["bg2"])
    draw = ImageDraw.Draw(image)
    _draw_glow_circles(draw, width, height, accent)

    header_h = int(88 * scale)
    draw.rectangle([(0, 0), (width, header_h)], fill=_blend(accent, style["bg"], 0.55))
    draw.rectangle([(0, 0), (width, max(4, int(6 * scale)))], fill=accent)

    badge_font = _load_font(FONT_BOLD, max(11, int(11 * scale)))
    badge_text = style["badge"]
    badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_w = badge_bbox[2] - badge_bbox[0] + int(28 * scale)
    badge_h = int(26 * scale)
    badge_x = (width - badge_w) // 2
    badge_y = int(14 * scale)
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=badge_h // 2,
        fill=_blend(accent, (0, 0, 0), 0.35),
        outline=accent,
        width=1,
    )
    draw.text(
        (badge_x + (badge_w - (badge_bbox[2] - badge_bbox[0])) // 2, badge_y + 4),
        badge_text,
        font=badge_font,
        fill=(255, 255, 255),
    )

    y = header_h + int(20 * scale)
    title_font = layout["title_font"]
    for line in layout["title_lines"]:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        draw.text(
            ((width - (bbox[2] - bbox[0])) // 2, y),
            line,
            font=title_font,
            fill=style["text"],
        )
        y += int(style["title_size"] * 1.12)

    if subtitulo:
        sub_font = _load_font(FONT_REGULAR, style["subtitle_size"])
        sub_lines = _wrap_text(subtitulo, sub_font, width - margin * 2, 2)
        for line in sub_lines:
            bbox = draw.textbbox((0, 0), line, font=sub_font)
            draw.text(
                ((width - (bbox[2] - bbox[0])) // 2, y + 6),
                line,
                font=sub_font,
                fill=style["subtext"],
            )
            y += int(style["subtitle_size"] * 1.35)
        y += int(8 * scale)

    y += int(16 * scale)
    inner_x = margin + int(8 * scale)
    inner_w = layout["inner_w"]
    body_font = layout["body_font"]
    heading_font = layout["heading_font"]

    for index, section in enumerate(sections):
        box_h = layout["section_heights"][index]
        box_bg = style["section_bg"]
        draw.rounded_rectangle(
            [(inner_x, y), (inner_x + inner_w + int(16 * scale), y + box_h)],
            radius=int(12 * scale),
            fill=box_bg,
            outline=accent,
            width=max(1, int(2 * scale)),
        )
        draw.rectangle(
            [(inner_x, y), (inner_x + int(6 * scale), y + box_h)],
            fill=accent,
        )

        icon_font = _load_font(FONT_BOLD, max(10, int(11 * scale)))
        icon_cx = inner_x + int(28 * scale)
        icon_cy = y + int(28 * scale)
        icon_r = int(18 * scale)
        _draw_section_icon(
            draw,
            x=icon_cx,
            y=icon_cy,
            radius=icon_r,
            label=section["icono"],
            accent=accent,
            font=icon_font,
        )

        text_x = inner_x + int(58 * scale)
        draw.text((text_x, y + int(14 * scale)), section["subtitulo"], font=heading_font, fill=style["section_heading"])

        content_lines = _wrap_text(section["contenido"], body_font, inner_w - int(56 * scale), 4)
        line_y = y + int(40 * scale)
        for line in content_lines:
            draw.text((text_x, line_y), line, font=body_font, fill=style["section_body"])
            line_y += int(24 * scale)

        y += box_h + int(14 * scale)

    footer_font = _load_font(FONT_REGULAR, style["footer_size"])
    mono_font = _load_font(FONT_MONO, max(10, style["footer_size"] - 1))
    footer_y = height - int(48 * scale)
    footer_bbox = draw.textbbox((0, 0), pie_pagina, font=footer_font)
    draw.text(
        ((width - (footer_bbox[2] - footer_bbox[0])) // 2, footer_y),
        pie_pagina,
        font=footer_font,
        fill=_pick_text_on(style["bg2"], style["subtext"], (230, 240, 230), (50, 60, 50)),
    )
    fecha = datetime.now().strftime("%d/%m/%Y · %H:%M")
    draw.text((width - margin, height - int(20 * scale)), fecha, font=mono_font, fill=(180, 190, 180))
    draw.rectangle([(0, height - max(4, int(6 * scale))), (width, height)], fill=accent)

    return image


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
    """Genera poster PNG. Calcula alto automático si el pedido no cabe."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    resolved_title = (titulo_principal or titulo or "Aviso importante").strip()
    sections = _normalize_sections(secciones, secciones_informativas, mensaje)
    if not sections:
        return {
            "success": False,
            "mensaje": "Indica al menos un mensaje o secciones_informativas para el poster.",
        }

    sub = subtitulo.strip() if subtitulo else None
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
        title=resolved_title,
        sections=sections,
        subtitulo=sub,
    )

    pie_text = pie_pagina or "GPTEnterprice · Comunicado interno"
    image = _render_poster_png(
        style=style,
        title=resolved_title,
        sections=sections,
        subtitulo=sub,
        pie_pagina=pie_text,
    )

    filename = f"poster_{uuid.uuid4().hex[:8]}.png"
    filepath = STORAGE_DIR / filename
    image.save(filepath, format="PNG", optimize=True)

    public_url = public_file_url(filename)
    result: dict[str, Any] = {
        "success": True,
        "archivo": filename,
        "formato": "png",
        "url": public_url,
        "ancho": style["width"],
        "alto": style["height"],
        "tema": style["theme_key"],
        "secciones": len(sections),
        "mensaje": f"Poster PNG '{resolved_title}' ({style['width']}×{style['height']}) generado.",
    }
    if style.get("alto_ajustado"):
        result["aviso"] = (
            f"El alto pedido era insuficiente; se ajustó automáticamente a {style['height']}px "
            "para que quepan título y secciones."
        )
    return result


def generar_estructura_poster(**kwargs: Any) -> dict[str, Any]:
    return generar_poster_alerta(**kwargs)
