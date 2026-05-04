param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [string]$BackupDir = "backups"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFile = Join-Path $BackupDir "buy_modern_$timestamp.dump"
$backupPath = Join-Path (Resolve-Path -LiteralPath $BackupDir) "buy_modern_$timestamp.dump"

cmd /c "docker compose -f `"$ComposeFile`" exec -T postgres sh -c 'pg_dump -U `"`$POSTGRES_USER`" -d `"`$POSTGRES_DB`" -Fc' > `"$backupPath`""

Write-Host "Backup written to $backupFile"
