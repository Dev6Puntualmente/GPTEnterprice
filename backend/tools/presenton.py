from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

import httpx

from config import settings

STORAGE_DIR = Path(settings.storage_dir)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"}
DEFAULT_GRADIENT_INSTRUCTIONS = (
    "Si no hay imágenes del usuario, usa fondos con degradados suaves (gradientes) "
    "en cada diapositiva. No uses fotos de stock ni ilustraciones generadas por IA. "
    "Mantén un estilo corporativo limpio."
)
# Presenton 0.8.x: "general" ya no existe en la imagen Docker; usar neo-* o education/code.
DEFAULT_PRESENTON_TEMPLATE = "neo-general"
LEGACY_BROKEN_TEMPLATES = frozenset({"general"})
KNOWN_TEMPLATE_IDS = (
    "neo-general",
    "neo-standard",
    "neo-modern",
    "neo-swift",
    "education",
    "code",
    "standard",
    "modern",
    "swift",
    "pitch-deck",
    "report",
    "product-overview",
)


def _presenton_base() -> str:
    return (settings.presenton_url or "").rstrip("/")


def _auth() -> tuple[str, str] | None:
    user = (settings.presenton_username or "").strip()
    password = (settings.presenton_password or "").strip()
    if user and password:
        return user, password
    return None


def _resolve_local_file(path_or_url: str) -> Path | None:
    """Resuelve ruta local desde storage/, ruta absoluta o URL /files/ del backend."""
    raw = (path_or_url or "").strip()
    if not raw:
        return None

    candidate = Path(raw)
    if candidate.is_file():
        return candidate

    storage_name = Path(raw).name
    in_storage = STORAGE_DIR / storage_name
    if in_storage.is_file():
        return in_storage

    base = settings.public_base_url.rstrip("/")
    if raw.startswith(f"{base}/files/"):
        name = raw.rsplit("/", 1)[-1]
        local = STORAGE_DIR / name
        if local.is_file():
            return local

    return None


def _fetch_presenton_templates(
    client: httpx.Client,
    base: str,
    auth: tuple[str, str],
) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []

    # Self-hosted: plantillas custom en DB (no existe /template/all de la nube).
    try:
        response = client.get(
            f"{base}/api/v1/ppt/templates",
            params={"page": 1, "page_size": 100},
            auth=auth,
        )
        if response.status_code < 400:
            data = response.json()
            if isinstance(data, dict):
                for item in data.get("items") or []:
                    if not isinstance(item, dict) or not item.get("id"):
                        continue
                    layout_count = item.get("layout_count")
                    templates.append(
                        {
                            "id": str(item["id"]),
                            "name": str(item.get("name") or item["id"]),
                            "total_layouts": layout_count if isinstance(layout_count, int) else 1,
                        }
                    )
    except Exception:
        pass

    if templates:
        return templates

    # Fallback: plantillas built-in vía API Next.js (/api/template?group=...)
    discovered: list[dict[str, Any]] = []
    for template_id in KNOWN_TEMPLATE_IDS:
        try:
            response = client.get(
                f"{base}/api/template",
                params={"group": template_id},
                auth=auth,
            )
            if response.status_code >= 400:
                continue
            payload = response.json()
            if isinstance(payload, dict) and payload.get("error"):
                continue
            layouts = payload.get("layouts") if isinstance(payload, dict) else None
            total = len(layouts) if isinstance(layouts, list) else 1
            discovered.append(
                {"id": template_id, "name": template_id, "total_layouts": total}
            )
        except Exception:
            continue
    return discovered


def _resolve_template_id(
    client: httpx.Client,
    base: str,
    auth: tuple[str, str],
    preferred: str | None,
) -> str | None:
    """Elige plantilla válida. 'general' falla en Presenton 0.8.x (plantilla eliminada)."""
    templates = _fetch_presenton_templates(client, base, auth)

    by_id = {str(t.get("id") or ""): t for t in templates if t.get("id")}
    by_name = {str(t.get("name") or "").lower(): t for t in templates if t.get("name")}

    want = (
        preferred
        or settings.presenton_default_template
        or DEFAULT_PRESENTON_TEMPLATE
    ).strip()
    if want and want not in LEGACY_BROKEN_TEMPLATES:
        if want in by_id:
            return want
        match = by_name.get(want.lower())
        if match:
            return str(match.get("id"))

    # Preferir plantillas con layouts cargados (menos fallos en export)
    with_layouts = [
        t for t in templates
        if isinstance(t.get("total_layouts"), int) and t.get("total_layouts", 0) > 0
    ]
    if with_layouts:
        return str(with_layouts[0].get("id"))

    for key in KNOWN_TEMPLATE_IDS:
        if key in by_id:
            return key
        if key in by_name:
            return str(by_name[key].get("id"))

    if templates:
        first = templates[0]
        return str(first.get("id")) if first.get("id") else None

    return DEFAULT_PRESENTON_TEMPLATE


def _template_export_error(detail: str) -> bool:
    lowered = detail.lower()
    return (
        "template" in lowered and "not found" in lowered
    ) or "failed to fetch or parse schema" in lowered


def _post_generate(
    client: httpx.Client,
    endpoint: str,
    auth: tuple[str, str],
    body: dict[str, Any],
) -> httpx.Response:
    """Genera presentación; reintenta con otra plantilla o PDF si falla export."""
    response = client.post(endpoint, json=body, auth=auth)
    if response.status_code < 400:
        return response

    detail = response.text
    if not _template_export_error(detail):
        return response

    failed_template = body.get("template")
    retry_templates = [
        tid
        for tid in KNOWN_TEMPLATE_IDS
        if tid != failed_template and tid not in LEGACY_BROKEN_TEMPLATES
    ]
    for template_id in retry_templates:
        body_retry = dict(body)
        body_retry["template"] = template_id
        response = client.post(endpoint, json=body_retry, auth=auth)
        if response.status_code < 400:
            return response

    # PDF a veces exporta cuando PPTX falla
    if body.get("export_as") == "pptx":
        body_pdf = dict(body)
        body_pdf["export_as"] = "pdf"
        body_pdf["template"] = DEFAULT_PRESENTON_TEMPLATE
        response = client.post(endpoint, json=body_pdf, auth=auth)
        if response.status_code < 400:
            return response

    return response


def _upload_files_to_presenton(
    client: httpx.Client,
    base: str,
    auth: tuple[str, str],
    archivos: list[str] | None,
) -> list[str]:
    """Sube imágenes del usuario a Presenton y devuelve los IDs para el campo files."""
    if not archivos:
        return []

    upload_url = f"{base}/api/v1/ppt/files/upload"
    uploaded: list[str] = []

    for item in archivos:
        local = _resolve_local_file(str(item))
        if local is None or local.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        with local.open("rb") as handle:
            response = client.post(
                upload_url,
                auth=auth,
                files={"files": (local.name, handle, "application/octet-stream")},
            )
        if response.status_code >= 400:
            continue
        try:
            data = response.json()
        except Exception:
            continue
        if isinstance(data, list):
            uploaded.extend(str(x) for x in data if x)
        elif isinstance(data, dict):
            for key in ("files", "file_ids", "ids"):
                values = data.get(key)
                if isinstance(values, list):
                    uploaded.extend(str(x) for x in values if x)
                    break
            if data.get("id"):
                uploaded.append(str(data["id"]))

    return uploaded


def _copy_generated_file(source_path: str) -> str | None:
    """Copia el PPTX/PDF generado a storage/ si la ruta existe en el mismo host."""
    if not source_path:
        return None
    src = Path(source_path)
    if not src.is_file():
        return None
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower() or ".pptx"
    dest = STORAGE_DIR / f"presentacion_{uuid.uuid4().hex[:10]}{ext}"
    shutil.copy2(src, dest)
    return f"{settings.public_base_url.rstrip('/')}/files/{dest.name}"


def generar_presentacion(
    contenido: str,
    titulo: str | None = None,
    num_diapositivas: int | str | float = 8,
    idioma: str = "Spanish",
    plantilla: str = DEFAULT_PRESENTON_TEMPLATE,
    tono: str = "professional",
    densidad: str = "standard",
    formato: str = "pptx",
    instrucciones: str | None = None,
    archivos: list[str] | None = None,
    imagenes: list[str] | None = None,
) -> dict[str, Any]:
    """
    Genera una presentación PPTX/PDF vía Presenton (self-hosted).
    Imágenes: el usuario puede subirlas (archivos/imagenes); si no hay ninguna,
    Presenton usa fondos en degradado (sin API de imágenes externa).
    """
    base = _presenton_base()
    if not base:
        return {
            "success": False,
            "mensaje": (
                "Presenton no está configurado. Define PRESENTON_URL, "
                "PRESENTON_USERNAME y PRESENTON_PASSWORD en el backend."
            ),
        }

    auth = _auth()
    if auth is None:
        return {
            "success": False,
            "mensaje": "Faltan credenciales Presenton (PRESENTON_USERNAME / PRESENTON_PASSWORD).",
        }

    text = (contenido or "").strip()
    if not text:
        return {"success": False, "mensaje": "Indica el contenido o tema de la presentación."}

    if titulo and titulo.strip():
        text = f"Título: {titulo.strip()}\n\n{text}"

    try:
        n_slides = int(float(num_diapositivas))
    except (ValueError, TypeError):
        n_slides = 8
    n_slides = max(3, min(n_slides, 30))

    export_as = (formato or "pptx").strip().lower()
    if export_as not in ("pptx", "pdf"):
        export_as = "pptx"

    user_files = list(archivos or []) + list(imagenes or [])
    merged_instructions = (instrucciones or "").strip()
    if not user_files and not merged_instructions:
        merged_instructions = DEFAULT_GRADIENT_INSTRUCTIONS
    elif not user_files and DEFAULT_GRADIENT_INSTRUCTIONS not in merged_instructions:
        merged_instructions = f"{merged_instructions}\n\n{DEFAULT_GRADIENT_INSTRUCTIONS}"

    body: dict[str, Any] = {
        "content": text,
        "n_slides": n_slides,
        "language": idioma or "Spanish",
        "tone": tono or "professional",
        "verbosity": densidad or "standard",
        "export_as": export_as,
        "include_title_slide": True,
    }
    if merged_instructions:
        body["instructions"] = merged_instructions

    endpoint = f"{base}/api/v1/ppt/presentation/generate"
    try:
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            template_id = _resolve_template_id(
                client,
                base,
                auth,
                plantilla or settings.presenton_default_template,
            )
            if template_id:
                body["template"] = template_id

            uploaded_ids = _upload_files_to_presenton(client, base, auth, user_files)
            if uploaded_ids:
                body["files"] = uploaded_ids
            response = _post_generate(client, endpoint, auth, body)
    except httpx.ConnectError:
        return {
            "success": False,
            "mensaje": f"No se pudo conectar a Presenton en {base}. ¿Está el contenedor arriba?",
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "mensaje": "Presenton tardó demasiado en generar la presentación (timeout 10 min).",
        }
    except Exception as exc:
        return {"success": False, "mensaje": f"Error llamando a Presenton: {exc}"}

    if response.status_code == 401:
        return {
            "success": False,
            "mensaje": "Credenciales Presenton rechazadas (401). Revisa usuario/contraseña.",
        }
    if response.status_code >= 400:
        detail = response.text[:500]
        if _template_export_error(detail):
            return {
                "success": False,
                "mensaje": (
                    "Presenton generó el contenido pero falló la exportación PPTX/PDF "
                    "(bug conocido v0.8.x en la API). La UI web funciona; la API puede fallar. "
                    "Actualiza Presenton o usa export_as=pdf. Detalle: " + detail[:200]
                ),
            }
        return {
            "success": False,
            "mensaje": f"Presenton respondió HTTP {response.status_code}: {detail}",
        }

    try:
        data = response.json()
    except Exception:
        return {"success": False, "mensaje": "Presenton devolvió una respuesta no JSON."}

    presentation_id = data.get("presentation_id")
    file_path = str(data.get("path") or "")
    edit_path = str(data.get("edit_path") or "")
    actual_format = export_as
    if file_path.lower().endswith(".pdf"):
        actual_format = "pdf"

    download_url = _copy_generated_file(file_path)
    edit_url = ""
    if not settings.presenton_internal:
        edit_url = edit_path
        if edit_path and not edit_path.startswith("http"):
            edit_url = f"{base}/{edit_path.lstrip('/')}"

    payload: dict[str, Any] = {
        "success": True,
        "presentation_id": presentation_id,
        "formato": actual_format,
        "diapositivas": n_slides,
        "imagenes_usuario": len(user_files),
        "fondo": "imagenes_usuario" if user_files else "degradados",
        "plantilla": body.get("template"),
        "mensaje": "Presentación generada con Presenton.",
    }
    if download_url:
        payload["url"] = download_url
        payload["archivo"] = Path(download_url).name
        payload["mensaje"] = f"Presentación {actual_format.upper()} lista para descargar."
    if edit_url:
        payload["editar_url"] = edit_url

    if not download_url:
        payload["mensaje"] = (
            "Presentación generada en Presenton. El archivo se entrega vía GPTEnterprice "
            "(los usuarios no acceden a Presenton directamente). "
            "Si no hay enlace de descarga, ejecuta el backend en el mismo servidor que Presenton."
        )
        if settings.presenton_internal:
            payload["nota_admin"] = (
                f"ID interno: {presentation_id}. Presenton solo en localhost."
            )
        elif file_path:
            payload["path_servidor"] = file_path

    return payload
