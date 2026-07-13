param(
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RootEnv = Join-Path $Root ".env"

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

function Stop-ProcessTree {
    param([int]$ProcessId, [string]$Reason)
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if (-not $proc) { return $false }
    Write-Host "Deteniendo PID $ProcessId ($Reason)" -ForegroundColor Yellow
    Write-Host "  $($proc.CommandLine)" -ForegroundColor DarkGray
    & taskkill /F /T /PID $ProcessId | Out-Null
    return $true
}

$stopped = @()

foreach ($procId in Get-PortListenerPids -TargetPort $Port) {
    if (Stop-ProcessTree -ProcessId $procId -Reason "puerto $Port") {
        $stopped += $procId
    }
}

Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -match 'GPTEnterprice\\backend' -and
        $_.CommandLine -match 'uvicorn' -and
        $_.CommandLine -match 'main:app'
    } |
    ForEach-Object {
        if ($stopped -notcontains $_.ProcessId) {
            if (Stop-ProcessTree -ProcessId $_.ProcessId -Reason "uvicorn GPTEnterprice huérfano") {
                $stopped += $_.ProcessId
            }
        }
    }

Start-Sleep -Milliseconds 400

$remaining = @(Get-PortListenerPids -TargetPort $Port)
if ($remaining.Count -eq 0) {
    if ($stopped.Count -gt 0) {
        Write-Host "Puerto $Port libre. Procesos detenidos: $($stopped -join ', ')" -ForegroundColor Green
    } else {
        Write-Host "Puerto $Port ya estaba libre." -ForegroundColor DarkGray
    }
    exit 0
}

Write-Host "Puerto $Port sigue en uso por: $($remaining -join ', ')" -ForegroundColor Red
exit 1
