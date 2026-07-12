param(
    [int]$Port = 0,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$RootEnv = Join-Path $Root ".env"

function Get-AgentPortFromEnv {
    if (-not (Test-Path $RootEnv)) { return 8100 }
    $line = Get-Content $RootEnv | Where-Object { $_ -match '^\s*AGENT_API_URL\s*=' } | Select-Object -First 1
    if ($line -match ':(\d+)\s*$') { return [int]$Matches[1] }
    return 8100
}

if ($Port -le 0) {
    $Port = Get-AgentPortFromEnv
}

function Get-PortListeners {
    param([int]$TargetPort)
    netstat -ano | Select-String ":$TargetPort\s" | ForEach-Object {
        if ($_ -match "\sLISTENING\s+(\d+)\s*$") {
            [pscustomobject]@{
                Pid = [int]$Matches[1]
                Line = $_.Line.Trim()
            }
        }
    }
}

$listeners = @(Get-PortListeners -TargetPort $Port | Sort-Object Pid -Unique)
if ($listeners.Count -gt 0 -and -not $Force) {
    Write-Host "Puerto $Port ya está en uso por $($listeners.Count) proceso(s):" -ForegroundColor Yellow
    foreach ($listener in $listeners) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.Pid)" -ErrorAction SilentlyContinue
        Write-Host "  PID $($listener.Pid) -> $($proc.CommandLine)" -ForegroundColor DarkYellow
    }
    Write-Host ""
    Write-Host "Detén los procesos duplicados antes de iniciar otro backend." -ForegroundColor Red
    Write-Host "Ejemplo: taskkill /F /T /PID $($listeners[0].Pid)" -ForegroundColor DarkGray
    Write-Host "O reinicia con: .\scripts\start-backend.ps1 -Force" -ForegroundColor DarkGray
    exit 1
}

Push-Location $Backend
try {
    $venvPython = $null
    foreach ($candidate in @("ServerVisor", ".venv")) {
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
    }

    & $venvPython -m pip install -r requirements.txt
    Copy-Item $RootEnv (Join-Path $Backend ".env") -Force

    Write-Host "Iniciando FastAPI Agent en http://127.0.0.1:$Port" -ForegroundColor Green
    Write-Host "Health: http://127.0.0.1:$Port/health" -ForegroundColor DarkGray
    Write-Host "Tools:  http://127.0.0.1:$Port/tools" -ForegroundColor DarkGray
    Write-Host "Next.js AGENT_API_URL debe coincidir: http://127.0.0.1:$Port" -ForegroundColor DarkGray

    # 127.0.0.1 evita WinError 10013 con 'localhost' en algunos Windows
    & $venvPython -m uvicorn main:app --reload --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}
