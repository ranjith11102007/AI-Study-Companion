param(
    [switch]$Watchdog,
    [int]$IntervalSeconds = 10
)

$ErrorActionPreference = "Stop"

$PgHome = if ($env:POSTGRES_HOME) { $env:POSTGRES_HOME } else { "C:\Users\RANJITH T\Desktop\yusuf\.local\postgres\pgsql" }
$PgData = if ($env:POSTGRES_DATA) { $env:POSTGRES_DATA } else { "C:\Users\RANJITH T\Desktop\yusuf\.local\postgres\data" }
$LogDir = Join-Path (Split-Path $PgHome -Parent) "logs"
$Bin = Join-Path $PgHome "bin"
$Port = 5432

function Start-Server {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
    $pidFile = Join-Path $PgData "postmaster.pid"
    $running = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($running) {
        taskkill /F /IM postgres.exe 2>&1 | Out-Null
        Start-Sleep -Seconds 3
    }
    if (Test-Path $pidFile) { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }
    $log = Join-Path $LogDir "pg_$(Get-Date -Format yyyyMMdd_HHmmss).log"
    & (Join-Path $Bin "pg_ctl.exe") -D $PgData -l $log -w -t 30 start -o "-c autovacuum=off"
    if ($LASTEXITCODE -ne 0) { throw "pg_ctl start failed (exit $LASTEXITCODE). See $log" }
}

function Test-Server {
    & (Join-Path $Bin "pg_isready.exe") -h 127.0.0.1 -p $Port -t 3 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
}

Start-Server
Write-Host "PostgreSQL started. Database: studymate on 127.0.0.1:$Port"

if ($Watchdog) {
    Write-Host "Watchdog mode: probing every $IntervalSeconds s; restarts automatically if unresponsive."
    while ($true) {
        Start-Sleep -Seconds $IntervalSeconds
        if (-not (Test-Server)) {
            Write-Host "[$(Get-Date -Format HH:mm:ss)] Server unresponsive - restarting..."
            try { Start-Server } catch { Write-Host "restart failed: $_" }
        }
    }
}
