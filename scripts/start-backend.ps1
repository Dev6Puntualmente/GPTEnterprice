param(
    [int]$Port = 8100
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"

Push-Location $Backend
try {
    $venvPython = $null
    foreach ($candidate in @(".venv", "ServerVisor")) {
        $pythonPath = Join-Path $Backend "$candidate\Scripts\python.exe"
        if (Test-Path $pythonPath) {
            $venvPython = $pythonPath
            break
        }
    }

    if (-not $venvPython) {
        Write-Host "Creando entorno virtual .venv..." -ForegroundColor Cyan
        python -m venv .venv
        $venvPython = Join-Path $Backend ".venv\Scripts\python.exe"
        & $venvPython -m pip install -r requirements.txt
    }

    Copy-Item (Join-Path $Root ".env") (Join-Path $Backend ".env") -ErrorAction SilentlyContinue
    Write-Host "Iniciando FastAPI Agent en http://localhost:$Port" -ForegroundColor Green
    Write-Host "Health: http://localhost:$Port/health" -ForegroundColor DarkGray
    Write-Host "Tools:  http://localhost:$Port/tools" -ForegroundColor DarkGray
    & $venvPython -m uvicorn main:app --reload --host 0.0.0.0 --port $Port
}
finally {
    Pop-Location
}
