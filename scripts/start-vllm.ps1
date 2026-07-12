param(
    [ValidateSet("smart", "fast", "both")]
    [string]$Mode = "both"
)

$ErrorActionPreference = "Stop"

function Start-VllmSmart {
    Write-Host "Iniciando Qwen2.5-7B en puerto 8001..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "vllm serve Qwen/Qwen2.5-7B-Instruct --port 8001 --gpu-memory-utilization 0.35 --tool-call-parser hermes"
    )
}

function Start-VllmFast {
    Write-Host "Iniciando Phi-3.5-mini en puerto 8002..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        "vllm serve microsoft/Phi-3.5-mini-instruct --port 8002 --gpu-memory-utilization 0.25"
    )
}

switch ($Mode) {
    "smart" { Start-VllmSmart }
    "fast"  { Start-VllmFast }
    "both"  { Start-VllmSmart; Start-Sleep -Seconds 2; Start-VllmFast }
}

Write-Host ""
Write-Host "VLLM iniciado. Verifica:" -ForegroundColor Green
Write-Host "  Smart: http://localhost:8001/v1/models"
Write-Host "  Fast:  http://localhost:8002/v1/models"
