#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-both}"

start_smart() {
  echo "Iniciando Qwen2.5-7B en puerto 8001..."
  vllm serve Qwen/Qwen2.5-7B-Instruct \
    --port 8001 \
    --gpu-memory-utilization 0.35 \
    --tool-call-parser hermes &
}

start_fast() {
  echo "Iniciando Phi-3.5-mini en puerto 8002..."
  vllm serve microsoft/Phi-3.5-mini-instruct \
    --port 8002 \
    --gpu-memory-utilization 0.25 &
}

case "$MODE" in
  smart) start_smart ;;
  fast) start_fast ;;
  both) start_smart; sleep 2; start_fast ;;
  *) echo "Uso: $0 [smart|fast|both]"; exit 1 ;;
esac

wait
