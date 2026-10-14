$ErrorActionPreference = "Continue"
$PG = "C:\Users\RANJITH T\Desktop\yusuf\.local\postgres"
$BIN = "$PG\pgsql\bin"
$DATA = "$PG\data"
$LOG = "$env:TEMP\studymate-runner.log"
$SCRIPT = "C:\Users\RANJITH T\Desktop\AI-Study-Companion\backend\scripts\db-speedrun.py"
$PY = "C:\Users\RANJITH T\Desktop\AI-Study-Companion\backend\.venv\Scripts\python.exe"

function Write-Log($msg) {
    Add-Content -Path $LOG -Value "[$(Get-Date -Format HH:mm:ss)] $msg"
}

Set-Content -Path $LOG -Value "[$(Get-Date -Format HH:mm:ss)] speedrun runner start"

for ($i = 1; $i -le 6; $i++) {
    taskkill /F /IM postgres.exe 2>&1 | Out-Null
    Start-Sleep -Seconds 4
    $pidFile = "$DATA\postmaster.pid"
    if (Test-Path $pidFile) { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }
    if (-not (Test-Path "$PG\logs")) { New-Item -ItemType Directory "$PG\logs" | Out-Null }
    $log = "$PG\logs\pg_$(Get-Date -Format HHmmss).log"
    & "$BIN\pg_ctl.exe" -D $DATA -l $log -w -t 30 start -o "-c autovacuum=off" 2>&1 | Out-Null
    Write-Log "attempt ${i}: pg_ctl rc=$LASTEXITCODE"
    & $PY $SCRIPT 2>&1 | ForEach-Object { Write-Log "  $_" }
    Write-Log "attempt ${i}: speedrun exit=$LASTEXITCODE"
    if ((Get-Content $LOG -Raw) -match "COMPLETE: database foundation ready") {
        Write-Log "SUCCESS"
        exit 0
    }
    Start-Sleep -Seconds 3
}
Write-Log "FAILED after 6 attempts"
exit 1
