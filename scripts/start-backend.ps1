param(
    [int]$Port = 8100
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"

Push-Location $Backend
try {
    if (-not (Test-Path ".venv")) {
        Write-Host "Creando entorno virtual Python..." -ForegroundColor Cyan
        python -m venv .venv
        .\.venv\Scripts\pip install -r requirements.txt
    }

    Copy-Item (Join-Path $Root ".env") (Join-Path $Backend ".env") -ErrorAction SilentlyContinue
    Write-Host "Iniciando FastAPI en puerto $Port..." -ForegroundColor Green
    .\.venv\Scripts\python -m uvicorn main:app --reload --host 0.0.0.0 --port $Port
}
finally {
    Pop-Location
}
