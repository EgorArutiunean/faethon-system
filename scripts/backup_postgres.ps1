param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [string]$EnvFile = ".env.production",
    [string]$BackupDir = "backups",
    [string]$MetricsFile = "",
    [ValidateRange(0, 3650)]
    [int]$RetentionDays = 14,
    [string]$ComposeProject = ""
)

$ErrorActionPreference = "Stop"

function Get-ContainerEnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($script:PostgresContainer) {
        $rawValue = & docker exec $script:PostgresContainer printenv $Name
    }
    else {
        $rawValue = & docker compose --env-file $EnvFile -f $ComposeFile exec -T postgres printenv $Name
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Cannot read $Name from the PostgreSQL container"
    }
    $value = ($rawValue | Out-String).Trim()
    if (-not $value) {
        throw "Variable $Name is empty in the PostgreSQL container"
    }
    if ($value -notmatch '^[A-Za-z_][A-Za-z0-9_-]*$') {
        throw "Variable $Name must be a safe PostgreSQL identifier"
    }
    return $value
}

function Write-BackupMetrics {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$AttemptSucceeded
    )

    if (-not $MetricsFile) {
        return
    }
    $metricsParent = Split-Path -Parent $MetricsFile
    if ($metricsParent -and -not (Test-Path -LiteralPath $metricsParent)) {
        New-Item -ItemType Directory -Path $metricsParent | Out-Null
    }
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $lastSuccess = $null
    if ($AttemptSucceeded) {
        $lastSuccess = $now
    }
    elseif (Test-Path -LiteralPath $MetricsFile -PathType Leaf) {
        $previous = Select-String -LiteralPath $MetricsFile -Pattern '^buy_modern_backup_last_success_timestamp_seconds\s+(\d+)$' | Select-Object -First 1
        if ($previous) {
            $lastSuccess = $previous.Matches[0].Groups[1].Value
        }
    }
    $lines = @(
        "# HELP buy_modern_backup_last_success_timestamp_seconds Unix timestamp of the latest validated backup."
        "# TYPE buy_modern_backup_last_success_timestamp_seconds gauge"
    )
    if ($null -ne $lastSuccess) {
        $lines += "buy_modern_backup_last_success_timestamp_seconds $lastSuccess"
    }
    $lines += @(
        "# HELP buy_modern_backup_last_attempt_success Whether the latest backup attempt succeeded."
        "# TYPE buy_modern_backup_last_attempt_success gauge"
        "buy_modern_backup_last_attempt_success $([int]$AttemptSucceeded)"
        "# HELP buy_modern_backup_last_attempt_timestamp_seconds Unix timestamp of the latest backup attempt."
        "# TYPE buy_modern_backup_last_attempt_timestamp_seconds gauge"
        "buy_modern_backup_last_attempt_timestamp_seconds $now"
    )
    $metricsTemporaryPath = "$MetricsFile.partial"
    $lines | Set-Content -LiteralPath $metricsTemporaryPath -Encoding ascii
    Move-Item -LiteralPath $metricsTemporaryPath -Destination $MetricsFile -Force
}

$temporaryPath = $null
$backupFile = $null
$backupLock = $null
$script:PostgresContainer = $null
try {
    if ($ComposeProject) {
        if ($ComposeProject -notmatch '^[A-Za-z0-9_.-]+$') {
            throw "ComposeProject contains invalid characters"
        }
        $containers = @(& docker ps --filter "label=com.docker.compose.project=$ComposeProject" --filter "label=com.docker.compose.service=postgres" --format "{{.ID}}")
        if ($LASTEXITCODE -ne 0 -or $containers.Count -ne 1 -or -not $containers[0]) {
            throw "Expected exactly one running postgres container for project $ComposeProject"
        }
        $script:PostgresContainer = $containers[0].Trim()
    }
    elseif (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        throw "Environment file not found: $EnvFile"
    }

    $postgresUser = Get-ContainerEnvValue -Name "POSTGRES_USER"
    $postgresDatabase = Get-ContainerEnvValue -Name "POSTGRES_DB"

    if (-not (Test-Path -LiteralPath $BackupDir)) {
        New-Item -ItemType Directory -Path $BackupDir | Out-Null
    }
    $resolvedBackupDir = (Resolve-Path -LiteralPath $BackupDir).Path
    $filesystemRoot = [System.IO.Path]::GetPathRoot($resolvedBackupDir)
    $trimChars = [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    if ($resolvedBackupDir.TrimEnd($trimChars) -eq $filesystemRoot.TrimEnd($trimChars)) {
        throw "Refusing to use the filesystem root as BackupDir"
    }

    $backupLock = [IO.File]::Open((Join-Path $resolvedBackupDir '.backup.lock'),
        [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupFile = Join-Path $BackupDir "buy_modern_$timestamp.dump"
    $backupPath = Join-Path $resolvedBackupDir "buy_modern_$timestamp.dump"
    if ((Test-Path -LiteralPath $backupPath) -or (Test-Path -LiteralPath "$backupPath.sha256")) {
        throw 'Backup timestamp already exists; refusing to overwrite'
    }
    $temporaryPath = "$backupPath.partial"

    if ($script:PostgresContainer) {
        cmd /d /s /c "docker exec -i `"$script:PostgresContainer`" pg_dump -U `"$postgresUser`" -d `"$postgresDatabase`" -Fc > `"$temporaryPath`""
    }
    else {
        cmd /d /s /c "docker compose --env-file `"$EnvFile`" -f `"$ComposeFile`" exec -T postgres pg_dump -U `"$postgresUser`" -d `"$postgresDatabase`" -Fc > `"$temporaryPath`""
    }
    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE"
    }
    if (-not (Test-Path -LiteralPath $temporaryPath -PathType Leaf) -or (Get-Item -LiteralPath $temporaryPath).Length -eq 0) {
        throw "Backup is empty: $temporaryPath"
    }

    if ($script:PostgresContainer) {
        cmd /d /s /c "docker exec -i `"$script:PostgresContainer`" pg_restore --list < `"$temporaryPath`" > NUL"
    }
    else {
        cmd /d /s /c "docker compose --env-file `"$EnvFile`" -f `"$ComposeFile`" exec -T postgres pg_restore --list < `"$temporaryPath`" > NUL"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Backup validation failed with exit code $LASTEXITCODE"
    }

    Move-Item -LiteralPath $temporaryPath -Destination $backupPath
    $checksum = (Get-FileHash -LiteralPath $backupPath -Algorithm SHA256).Hash.ToLowerInvariant()
    "$checksum  $(Split-Path -Leaf $backupPath)" | Set-Content -LiteralPath "$backupPath.sha256" -Encoding ascii

    if ($RetentionDays -gt 0) {
        $cutoff = [DateTime]::UtcNow.AddDays(-$RetentionDays)
        Get-ChildItem -LiteralPath $resolvedBackupDir -File |
            Where-Object {
                $_.Name -match '^buy_modern_\d{8}-\d{6}\.dump(\.sha256)?$' -and
                $_.LastWriteTimeUtc -lt $cutoff
            } |
            Remove-Item -Force
    }
    Write-BackupMetrics -AttemptSucceeded $true
}
catch {
    try {
        Write-BackupMetrics -AttemptSucceeded $false
    }
    catch {
        Write-Warning "Could not publish failed backup metric: $($_.Exception.Message)"
    }
    throw
}
finally {
    if ($temporaryPath -and (Test-Path -LiteralPath $temporaryPath)) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
    if ($backupLock) { $backupLock.Dispose() }
}

Write-Host "Backup written to $backupFile"
Write-Host "Checksum written to $backupFile.sha256"
if ($MetricsFile) {
    Write-Host "Backup freshness metric written to $MetricsFile"
}
Write-Host "Retention applied: $RetentionDays days"
