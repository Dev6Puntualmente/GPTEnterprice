#!/usr/bin/env bash
# Presenton self-hosted — vLLM OpenAI-compatible + configuración por variables.
#
# DAEMON: Docker con --restart unless-stopped (no PM2). Al reiniciar el servidor,
# Docker levanta Presenton solo si el servicio docker está activo:
#   systemctl enable docker
#
# SEGURIDAD: no expongas :5001 a Internet sin necesidad. Ideal: solo IP interna
# o VPN; si es público, usa contraseña fuerte + firewall del proveedor.
#
# CONFIGURABLE (env del contenedor):
#   LLM / modelo / URL / API key  → CUSTOM_LLM_* o LLM=ollama|openai|...
#   Imágenes                      → DISABLE_IMAGE_GENERATION o IMAGE_PROVIDER + keys
#   UI editable                   → CAN_CHANGE_KEYS=true (admin cambia en Ajustes)
#
# Política actual empresa: sin API de imágenes; degradados o imágenes del usuario.

set -euo pipefail

PORT="${PRESENTON_PORT:-5001}"
DATA_DIR="${PRESENTON_DATA:-/opt/presenton/app_data}"
IMAGE_PROVIDER="${IMAGE_PROVIDER:-pexels}"
DISABLE_IMAGES="${DISABLE_IMAGE_GENERATION:-true}"
CAN_CHANGE_KEYS="${CAN_CHANGE_KEYS:-true}"

mkdir -p "$DATA_DIR"

docker rm -f presenton 2>/dev/null || true

IMAGE_ENV=()
if [[ "${DISABLE_IMAGES}" == "true" ]]; then
  IMAGE_ENV+=(-e "DISABLE_IMAGE_GENERATION=true")
else
  IMAGE_ENV+=(-e "IMAGE_PROVIDER=${IMAGE_PROVIDER}")
  case "${IMAGE_PROVIDER}" in
    pexels)
      IMAGE_ENV+=(-e "PEXELS_API_KEY=${PEXELS_API_KEY:?PEXELS_API_KEY requerido para pexels}")
      ;;
    pixabay)
      IMAGE_ENV+=(-e "PIXABAY_API_KEY=${PIXABAY_API_KEY:?PIXABAY_API_KEY requerido para pixabay}")
      ;;
    gemini_flash|nanobanana_pro)
      IMAGE_ENV+=(-e "GOOGLE_API_KEY=${GOOGLE_API_KEY:?GOOGLE_API_KEY requerido}")
      ;;
    dall-e-3|gpt-image-1.5)
      IMAGE_ENV+=(-e "OPENAI_API_KEY=${OPENAI_API_KEY:?OPENAI_API_KEY requerido}")
      ;;
    comfyui)
      IMAGE_ENV+=(-e "COMFYUI_URL=${COMFYUI_URL:?COMFYUI_URL requerido}")
      IMAGE_ENV+=(-e "COMFYUI_WORKFLOW=${COMFYUI_WORKFLOW:?COMFYUI_WORKFLOW requerido}")
      ;;
    openai_compatible)
      IMAGE_ENV+=(-e "OPENAI_COMPAT_IMAGE_BASE_URL=${OPENAI_COMPAT_IMAGE_BASE_URL:?requerido}")
      IMAGE_ENV+=(-e "OPENAI_COMPAT_IMAGE_API_KEY=${OPENAI_COMPAT_IMAGE_API_KEY:-}")
      IMAGE_ENV+=(-e "OPENAI_COMPAT_IMAGE_MODEL=${OPENAI_COMPAT_IMAGE_MODEL:?requerido}")
      ;;
    open_webui)
      IMAGE_ENV+=(-e "OPEN_WEBUI_IMAGE_URL=${OPEN_WEBUI_IMAGE_URL:?requerido}")
      IMAGE_ENV+=(-e "OPEN_WEBUI_IMAGE_API_KEY=${OPEN_WEBUI_IMAGE_API_KEY:-}")
      ;;
    *)
      echo "IMAGE_PROVIDER desconocido: ${IMAGE_PROVIDER}" >&2
      exit 1
      ;;
  esac
fi

docker run -d \
  --name presenton \
  --restart unless-stopped \
  -p "${PORT}:80" \
  -e CAN_CHANGE_KEYS="${CAN_CHANGE_KEYS}" \
  -e LLM="custom" \
  -e CUSTOM_LLM_URL="${CUSTOM_LLM_URL:?CUSTOM_LLM_URL requerido}" \
  -e CUSTOM_LLM_API_KEY="${CUSTOM_LLM_API_KEY:-}" \
  -e CUSTOM_MODEL="${CUSTOM_MODEL:-Qwen/Qwen2.5-3B-Instruct}" \
  -e AUTH_USERNAME="${AUTH_USERNAME:-admin}" \
  -e AUTH_PASSWORD="${AUTH_PASSWORD:?AUTH_PASSWORD requerido}" \
  "${IMAGE_ENV[@]}" \
  -v "${DATA_DIR}:/app_data" \
  ghcr.io/presenton/presenton:latest

echo "Presenton UI: http://$(hostname -I | awk '{print $1}'):${PORT}"
echo "Daemon: Docker --restart unless-stopped (no PM2)"
echo "CAN_CHANGE_KEYS=${CAN_CHANGE_KEYS}"
if [[ "${DISABLE_IMAGES}" == "true" ]]; then
  echo "Imágenes: desactivadas (DISABLE_IMAGE_GENERATION=true)"
else
  echo "Imágenes: ${IMAGE_PROVIDER}"
fi
