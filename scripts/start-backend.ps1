param(
    [int]$Port = 0,
    [switch]$Reload,
    [switch]$NoKill
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$RootEnv = Join-Path $Root ".env"
$StopScript = Join-Path $PSScriptRoot "stop-backend.ps1"

function Get-AgentPortFromEnv {
    if (-not (Test-Path $RootEnv)) { return 8101 }
    $line = Get-Content $RootEnv | Where-Object { $_ -match '^\s*AGENT_API_URL\s*=' } | Select-Object -First 1
    if ($line -match ':(\d+)') { return [int]$Matches[1] }
    return 8101
}

if ($Port -le 0) {
    $Port = Get-AgentPortFromEnv
}

function Get-PortListenerPids {
    param([int]$TargetPort)
    netstat -ano | Select-String ":$TargetPort\s" | ForEach-Object {
        if ($_ -match "\sLISTENING\s+(\d+)\s*$") {
            [int]$Matches[1]
        }
    } | Sort-Object -Unique
}

if (-not $NoKill) {
    $existing = @(Get-PortListenerPids -TargetPort $Port)
    if ($existing.Count -gt 0) {
        Write-Host "Puerto $Port ocupado por $($existing.Count) proceso(s). Liberando..." -ForegroundColor Yellow
        & $StopScript -Port $Port
        if ($LASTEXITCODE -ne 0) {
            Write-Host "No se pudo liberar el puerto $Port." -ForegroundColor Red
            exit 1
        }
    }
}

function Get-TextFileMd5 {
    param([string]$Path)
    $md5 = [System.Security.Cryptography.MD5]::Create()
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        try {
            $bytes = $md5.ComputeHash($stream)
            return ([BitConverter]::ToString($bytes) -replace '-', '').ToLower()
        }
        finally {
            $stream.Close()
        }
    }
    finally {
        $md5.Dispose()
    }
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

    $reqPath = Join-Path $Backend "requirements.txt"
    $reqHash = Get-TextFileMd5 -Path $reqPath
    $hashFile = Join-Path $Backend ".requirements.md5"
    $prevHash = if (Test-Path $hashFile) { (Get-Content $hashFile -Raw).Trim() } else { "" }
    if ($reqHash -ne $prevHash) {
        Write-Host "Actualizando dependencias Python..." -ForegroundColor Cyan
        & $venvPython -m pip install -q -r requirements.txt
        Set-Content -Path $hashFile -Value $reqHash -NoNewline
    }
    $backendEnv = Join-Path $Backend ".env"
    if (-not (Test-Path $backendEnv)) {
        Copy-Item $RootEnv $backendEnv -Force
    }

    $reloadHint = if ($Reload) { " (reload activo: 2 procesos Python)" } else { " (1 proceso)" }
    Write-Host "Iniciando FastAPI Agent en http://127.0.0.1:$Port$reloadHint" -ForegroundColor Green
    Write-Host "Health: http://127.0.0.1:$Port/health" -ForegroundColor DarkGray
    Write-Host "Detener: .\scripts\stop-backend.ps1" -ForegroundColor DarkGray

    $uvicornArgs = @(
        "-m", "uvicorn", "main:app",
        "--host", "127.0.0.1",
        "--port", "$Port"
    )
    if ($Reload) {
        $uvicornArgs += "--reload"
    }

    & $venvPython @uvicornArgs
}
finally {
    Pop-Location
}
