#Requires -Version 7.0
param(
    [string]$SshTarget,
    [string]$IdentityFile,
    [string]$ResticExe = 'restic.exe',
    [string]$BackupRoot = 'C:/Users/Egor/Projects/BuyModern-backups',
    [switch]$InitializeRepository,
    [switch]$VerifyRoundTrip,
    [Security.SecureString]$RepositoryPassword
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-BackupBasename {
    param([string]$Name)
    if ($Name -cnotmatch '\Abuy_modern_[0-9]{8}-[0-9]{6}\.dump\z') {
        throw 'The server returned an invalid backup basename.'
    }
}

function ConvertFrom-BackupList {
    param([string]$Text)
    if ($Text.Length -eq 0) { return }
    $lines = $Text.Replace("`r`n", "`n").Split("`n")
    if ($lines[-1] -eq '') { $lines = $lines[0..($lines.Length - 2)] }
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($line in $lines) {
        Assert-BackupBasename $line
        if (-not $seen.Add($line)) { throw 'The server returned duplicate backup names.' }
    }
    $lines | Sort-Object
}

function Get-ExpectedBackupHash {
    param([string]$Text, [string]$Basename)
    Assert-BackupBasename $Basename
    $match = [regex]::Match($Text, '\A([0-9a-f]{64})  (buy_modern_[0-9]{8}-[0-9]{6}\.dump)(?:\r?\n)?\z')
    if (-not $match.Success -or $match.Groups[2].Value -cne $Basename) {
        throw 'Invalid checksum sidecar: expected one SHA-256 line for this exact backup.'
    }
    $match.Groups[1].Value
}

function Read-BoundedUtf8 {
    param([string]$Path, [long]$MaximumBytes)
    if ((Get-Item -LiteralPath $Path).Length -gt $MaximumBytes) {
        throw 'A protocol response exceeded its size limit.'
    }
    [Text.UTF8Encoding]::new($false, $true).GetString([IO.File]::ReadAllBytes($Path))
}

function Assert-NoReparseAncestors {
    param([string]$Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Backup, repository and identity paths must not traverse reparse points.'
            }
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}

function Set-PrivateBackupDirectory {
    param([string]$Path)
    Assert-NoReparseAncestors $Path
    if ((Test-Path -LiteralPath $Path) -and -not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw 'A required backup directory is occupied by a file.'
    }
    [void][IO.Directory]::CreateDirectory($Path)
    $security = [Security.AccessControl.DirectorySecurity]::new()
    $security.SetAccessRuleProtection($true, $false)
    $current = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $system = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
    $security.SetOwner($current)
    foreach ($sid in @($current, $system)) {
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [Security.AccessControl.FileSystemRights]::FullControl,
            ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
                [Security.AccessControl.InheritanceFlags]::ObjectInherit),
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow)
        [void]$security.AddAccessRule($rule)
    }
    [IO.FileSystemAclExtensions]::SetAccessControl([IO.DirectoryInfo]::new($Path), $security)
}

function Test-BackupPasswordEqual {
    param([Security.SecureString]$First, [Security.SecureString]$Second)
    if ($null -eq $First -or $null -eq $Second) { return $false }
    $firstPointer = [IntPtr]::Zero
    $secondPointer = [IntPtr]::Zero
    try {
        $firstPointer = [Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($First)
        $secondPointer = [Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($Second)
        $difference = $First.Length -bxor $Second.Length
        for ($index = 0; $index -lt [Math]::Min($First.Length, $Second.Length); $index++) {
            $difference = $difference -bor (
                [Runtime.InteropServices.Marshal]::ReadInt16($firstPointer, $index * 2) -bxor
                [Runtime.InteropServices.Marshal]::ReadInt16($secondPointer, $index * 2))
        }
        return ($difference -eq 0)
    }
    finally {
        if ($firstPointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($firstPointer)
        }
        if ($secondPointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($secondPointer)
        }
    }
}

function Initialize-BackupStreamHelper {
    if ('BuyModernBackup.BoundedStream' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
namespace BuyModernBackup {
    public static class BoundedStream {
        public static async Task CopyAsync(Stream input, Stream output, long limit, CancellationToken token) {
            byte[] buffer = new byte[65536];
            long total = 0;
            int count;
            while ((count = await input.ReadAsync(buffer, 0, buffer.Length, token).ConfigureAwait(false)) != 0) {
                if (count > limit - total) throw new InvalidDataException("Child output exceeded its limit.");
                total += count;
                await output.WriteAsync(buffer, 0, count, token).ConfigureAwait(false);
            }
        }
    }
}
'@
}

function Invoke-BackupChildProcess {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$WorkingDirectory,
        [string]$OutputFile,
        [long]$MaximumBytes,
        [Security.SecureString]$Password,
        [int]$TimeoutSeconds = 900
    )
    Initialize-BackupStreamHelper
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Executable
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.RedirectStandardInput = $true
    foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add($argument) }
    # The selected local repository and prompted password must be authoritative.
    # Do not pass ambient RESTIC_PASSWORD_COMMAND/FILE or RESTIC_REPOSITORY_FILE
    # to either child, and never modify the parent process environment.
    foreach ($key in @($startInfo.Environment.Keys)) {
        if ($key -like 'RESTIC_*') { [void]$startInfo.Environment.Remove($key) }
    }
    $passwordPointer = [IntPtr]::Zero
    $process = [Diagnostics.Process]::new()
    $started = $false
    $outputStream = $null
    $outputTask = $null
    $errorTask = $null
    $cancellation = [Threading.CancellationTokenSource]::new()
    try {
        if ($null -ne $Password) {
            $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($Password)
            $startInfo.Environment['RESTIC_PASSWORD'] =
                [Runtime.InteropServices.Marshal]::PtrToStringUni($passwordPointer)
        }
        $outputStream = [IO.File]::Open($OutputFile, [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write, [IO.FileShare]::None)
        $process.StartInfo = $startInfo
        if (-not $process.Start()) { throw 'Cannot start a required backup tool.' }
        $started = $true
        $process.StandardInput.Close()
        $outputTask = [BuyModernBackup.BoundedStream]::CopyAsync(
            $process.StandardOutput.BaseStream, $outputStream, $MaximumBytes, $cancellation.Token)
        # Drain stderr concurrently without emitting child diagnostics, which may
        # contain remote-controlled text. Excessive stderr also aborts the job.
        $errorTask = [BuyModernBackup.BoundedStream]::CopyAsync(
            $process.StandardError.BaseStream, [IO.Stream]::Null, 1048576, $cancellation.Token)
        $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
        while (-not $process.WaitForExit(100)) {
            if ($outputTask.IsFaulted -or $errorTask.IsFaulted) {
                throw 'A backup tool response exceeded its size limit or could not be written.'
            }
            if ([DateTime]::UtcNow -gt $deadline) { throw 'A backup tool exceeded its time limit.' }
        }
        $streams = [Threading.Tasks.Task]::WhenAll([Threading.Tasks.Task[]]@($outputTask, $errorTask))
        if (-not $streams.Wait(10000)) { throw 'A backup tool did not close its output streams.' }
        [void]$streams.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) { throw "A required backup tool failed (exit $($process.ExitCode))." }
    }
    finally {
        $cancellation.Cancel()
        if ($started -and -not $process.HasExited) {
            $process.Kill($true)
            [void]$process.WaitForExit(5000)
        }
        if ($null -ne $outputTask -and $null -ne $errorTask) {
            try {
                [void][Threading.Tasks.Task]::WhenAll([Threading.Tasks.Task[]]@($outputTask, $errorTask)).Wait(5000)
            }
            catch { } # Preserve the original process/transfer error after cancellation.
        }
        if ($null -ne $outputStream) { $outputStream.Dispose() }
        [void]$startInfo.Environment.Remove('RESTIC_PASSWORD')
        if ($passwordPointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($passwordPointer)
        }
        $process.Dispose()
        $cancellation.Dispose()
    }
}

function Get-BackupSnapshots {
    param([string]$Text, [string]$SourceTag)
    $parsed = ConvertFrom-Json -InputObject $Text -NoEnumerate
    if ($parsed -isnot [array]) { throw 'Restic returned an invalid snapshot listing.' }
    foreach ($snapshot in $parsed) {
        if ($snapshot.id -cnotmatch '\A[0-9a-f]{64}\z') {
            throw 'Restic returned an invalid snapshot identifier.'
        }
        $tags = @($snapshot.tags)
        if ($tags -cnotcontains 'buy-modern-staging' -or $tags -cnotcontains $SourceTag) { continue }
        foreach ($tag in $tags) {
            if ($tag -cmatch '\Abuy_modern_[0-9]{8}-[0-9]{6}\.dump\z') {
                [pscustomobject]@{ backup = $tag; snapshot = $snapshot.id }
            }
        }
    }
}

function Invoke-BackupRoundTripCheck {
    param(
        [string]$ResticExecutable,
        [string[]]$ResticArguments,
        [string]$SnapshotId,
        [string]$Basename,
        [string]$ExpectedHash,
        [string]$WorkingDirectory,
        [Collections.Generic.List[string]]$OwnedFiles,
        [Security.SecureString]$Password
    )
    Assert-BackupBasename $Basename
    if ($SnapshotId -cnotmatch '\A[0-9a-f]{64}\z') { throw 'Invalid snapshot identifier for round-trip verification.' }
    $roundTripPath = Join-Path $WorkingDirectory "roundtrip-$Basename"
    $OwnedFiles.Add($roundTripPath)
    Invoke-BackupChildProcess $ResticExecutable ($ResticArguments + @('dump', $SnapshotId, $Basename)) $WorkingDirectory $roundTripPath 10737418240 $Password
    $roundTripHash = (Get-FileHash -LiteralPath $roundTripPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($roundTripHash -cne $ExpectedHash) { throw 'The encrypted snapshot failed its round-trip SHA-256 check.' }
    Assert-NoReparseAncestors $roundTripPath
    [IO.File]::Delete($roundTripPath)
}

function Invoke-StagingBackupPull {
    param(
        [string]$SshTarget,
        [string]$IdentityFile,
        [string]$ResticExecutable,
        [string]$SshExecutable,
        [string]$BackupRoot,
        [bool]$InitializeRepository,
        [bool]$VerifyRoundTrip = $false,
        [Security.SecureString]$Password,
        [Security.SecureString]$ConfirmationPassword
    )
    if (-not $IsWindows) { throw 'This backup client requires Windows and PowerShell 7 or newer.' }
    if ($SshTarget -cnotmatch '\A[a-z_][a-z0-9_-]{0,31}@[A-Za-z0-9][A-Za-z0-9.-]{0,252}\z') {
        throw 'SshTarget must be an explicit user@host without options, ports or shell syntax.'
    }
    if ($null -eq $Password -or $Password.Length -eq 0) { throw 'A nonempty repository password is required.' }
    if ($InitializeRepository -and $Password.Length -lt 16) {
        throw 'A new repository requires a recovery passphrase of at least 16 characters.'
    }
    if ($InitializeRepository -and -not (Test-BackupPasswordEqual $Password $ConfirmationPassword)) {
        throw 'Repository password confirmation did not match.'
    }
    if (-not [IO.Path]::IsPathFullyQualified($IdentityFile) -or
        -not (Test-Path -LiteralPath $IdentityFile -PathType Leaf)) {
        throw 'IdentityFile must identify an existing absolute local SSH identity path.'
    }
    Assert-NoReparseAncestors $IdentityFile
    if (-not [IO.Path]::IsPathFullyQualified($BackupRoot)) { throw 'BackupRoot must be an absolute local path.' }
    $root = [IO.Path]::GetFullPath($BackupRoot).TrimEnd([char[]]'\/')
    if ($root -eq [IO.Path]::GetPathRoot($root).TrimEnd([char[]]'\/') -or $root.StartsWith('\\')) {
        throw 'BackupRoot must be a dedicated local directory, not a drive root or network share.'
    }
    Assert-NoReparseAncestors $root
    $repository = Join-Path $root 'repository'
    $incomingRoot = Join-Path $root '.incoming'
    Assert-NoReparseAncestors $repository
    Assert-NoReparseAncestors $incomingRoot
    if ($InitializeRepository -and (Test-Path -LiteralPath $repository)) {
        throw 'Repository already exists. Inspect it and omit InitializeRepository for an existing repository.'
    }
    if (-not $InitializeRepository -and -not (Test-Path -LiteralPath (Join-Path $repository 'config') -PathType Leaf)) {
        throw 'No initialized repository was found. Explicit initialization is required for a new repository.'
    }

    Set-PrivateBackupDirectory $root
    $lockPath = Join-Path $root '.pull.lock'
    Assert-NoReparseAncestors $lockPath
    $lock = $null
    $temporaryDirectory = $null
    $ownedFiles = [Collections.Generic.List[string]]::new()
    try {
        try {
            $lock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate,
                [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        }
        catch { throw 'Another pull is running or the local backup lock is inaccessible.' }
        Set-PrivateBackupDirectory $incomingRoot
        $temporaryDirectory = Join-Path $incomingRoot ([Guid]::NewGuid().ToString('N'))
        Set-PrivateBackupDirectory $temporaryDirectory
        $sequence = 0
        $sourceTag = "source:$SshTarget"
        $resticBase = @('--repo', $repository, '--no-cache')
        $sshBase = @('-F', 'NUL', '-T', '-n', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'IdentitiesOnly=yes', '-o', 'ClearAllForwardings=yes', '-o', 'ConnectTimeout=15',
            '-o', 'ConnectionAttempts=1', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=3',
            '-i', [IO.Path]::GetFullPath($IdentityFile), $SshTarget)
        if ($InitializeRepository) {
            # Check again while holding the lock. Never initialize an existing
            # directory, including an empty or partially initialized one.
            if (Test-Path -LiteralPath $repository) { throw 'Repository appeared before initialization; refusing to overwrite it.' }
            Set-PrivateBackupDirectory $repository
            $output = Join-Path $temporaryDirectory "restic-$sequence.json"
            $sequence++
            $ownedFiles.Add($output)
            Invoke-BackupChildProcess $ResticExecutable ($resticBase + @('init', '--json')) $temporaryDirectory $output 1048576 $Password
        }
        $output = Join-Path $temporaryDirectory "restic-$sequence.json"
        $sequence++
        $ownedFiles.Add($output)
        Invoke-BackupChildProcess $ResticExecutable ($resticBase + @('snapshots', '--json', '--tag', 'buy-modern-staging')) $temporaryDirectory $output 8388608 $Password
        $existing = @(Get-BackupSnapshots (Read-BoundedUtf8 $output 8388608) $sourceTag)
        $known = [Collections.Generic.Dictionary[string, object]]::new([StringComparer]::Ordinal)
        foreach ($snapshot in $existing) { $known[$snapshot.backup] = $snapshot }

        $listPath = Join-Path $temporaryDirectory 'server-list.txt'
        $ownedFiles.Add($listPath)
        Invoke-BackupChildProcess $SshExecutable ($sshBase + @('list')) $temporaryDirectory $listPath 65536 $null 120
        $names = @(ConvertFrom-BackupList (Read-BoundedUtf8 $listPath 65536))
        if ($names.Count -eq 0) { throw 'No complete validated backups are available on the server.' }
        $completed = [Collections.Generic.List[object]]::new()
        $verifiedSnapshots = [Collections.Generic.List[object]]::new()
        $roundTripVerified = 0
        $skipped = 0
        foreach ($name in $names) {
            if ($known.ContainsKey($name) -and -not $VerifyRoundTrip) { $skipped++; continue }
            $sidecarPath = Join-Path $temporaryDirectory "$name.sha256"
            $dumpPath = Join-Path $temporaryDirectory $name
            $ownedFiles.Add($sidecarPath)
            $ownedFiles.Add($dumpPath)
            Invoke-BackupChildProcess $SshExecutable ($sshBase + @('get', "$name.sha256")) $temporaryDirectory $sidecarPath 256 $null
            $expected = Get-ExpectedBackupHash (Read-BoundedUtf8 $sidecarPath 256) $name
            if ($known.ContainsKey($name)) {
                # A failed verification can leave a valid snapshot behind. An
                # explicit verification retry must re-check it, not silently
                # turn its presence into a successful no-op.
                Invoke-BackupRoundTripCheck $ResticExecutable $resticBase $known[$name].snapshot $name $expected $temporaryDirectory $ownedFiles $Password
                $roundTripVerified++
                $verifiedSnapshots.Add($known[$name])
                $skipped++
                Assert-NoReparseAncestors $sidecarPath
                [IO.File]::Delete($sidecarPath)
                continue
            }
            Invoke-BackupChildProcess $SshExecutable ($sshBase + @('get', $name)) $temporaryDirectory $dumpPath 10737418240 $null
            if ((Get-Item -LiteralPath $dumpPath).Length -eq 0) { throw 'The downloaded dump is empty.' }
            $actual = (Get-FileHash -LiteralPath $dumpPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actual -cne $expected) { throw 'The downloaded dump does not match its SHA-256 sidecar.' }
            $output = Join-Path $temporaryDirectory "restic-$sequence.json"
            $sequence++
            $ownedFiles.Add($output)
            Invoke-BackupChildProcess $ResticExecutable ($resticBase + @('backup', '--json', '--tag', 'buy-modern-staging',
                '--tag', $sourceTag, '--tag', $name, '--', $name, "$name.sha256")) $temporaryDirectory $output 16777216 $Password
            $output = Join-Path $temporaryDirectory "restic-$sequence.json"
            $sequence++
            $ownedFiles.Add($output)
            Invoke-BackupChildProcess $ResticExecutable ($resticBase + @('snapshots', '--json', '--tag', "buy-modern-staging,$name")) $temporaryDirectory $output 8388608 $Password
            $verified = @(Get-BackupSnapshots (Read-BoundedUtf8 $output 8388608) $sourceTag | Where-Object backup -CEQ $name)
            if ($verified.Count -eq 0) { throw 'Restic did not confirm the encrypted backup snapshot.' }
            if ($VerifyRoundTrip) {
                Invoke-BackupRoundTripCheck $ResticExecutable $resticBase $verified[-1].snapshot $name $expected $temporaryDirectory $ownedFiles $Password
                $roundTripVerified++
                $verifiedSnapshots.Add($verified[-1])
            }
            $completed.Add($verified[-1])
            $known[$name] = $verified[-1]
            # Retain plaintext only for this pair's transfer and encryption.
            foreach ($path in @($dumpPath, $sidecarPath)) {
                Assert-NoReparseAncestors $path
                [IO.File]::Delete($path)
            }
        }
        [pscustomobject]@{
            status = 'success'
            available = $names.Count
            encrypted = $completed.Count
            skipped = $skipped
            round_trip_verified = $roundTripVerified
            snapshots = @($completed.ToArray())
            verified_snapshots = @($verifiedSnapshots.ToArray())
            completed_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
        }
    }
    finally {
        # Delete only files this invocation created beneath its own GUID staging
        # directory. Never recursively remove BackupRoot, .incoming or repository.
        if ($temporaryDirectory) {
            try {
                $expectedParent = [IO.Path]::GetFullPath($incomingRoot).TrimEnd('\')
                $actualParent = [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($temporaryDirectory))
                if (-not [StringComparer]::OrdinalIgnoreCase.Equals($expectedParent, $actualParent) -or
                    [IO.Path]::GetFileName($temporaryDirectory) -cnotmatch '\A[0-9a-f]{32}\z') {
                    throw 'Temporary directory ownership validation failed.'
                }
                Assert-NoReparseAncestors $temporaryDirectory
                foreach ($path in $ownedFiles) {
                    if (-not [StringComparer]::OrdinalIgnoreCase.Equals([IO.Path]::GetDirectoryName($path), $temporaryDirectory)) {
                        throw 'Temporary file ownership validation failed.'
                    }
                    if (Test-Path -LiteralPath $path) {
                        Assert-NoReparseAncestors $path
                        [IO.File]::Delete($path)
                    }
                }
                [IO.Directory]::Delete($temporaryDirectory, $false)
            }
            catch { Write-Warning 'Could not completely remove this invocation''s private temporary directory; inspect .incoming.' }
        }
        if ($null -ne $lock) { $lock.Dispose() }
    }
}

# Dot-sourcing exposes validation/core functions for synthetic tests without any
# filesystem, SSH or repository action.
if ($MyInvocation.InvocationName -eq '.') { return }

$confirmation = $null
$ownsPassword = $false
try {
    if (-not $IsWindows) { throw 'This backup client requires Windows and PowerShell 7 or newer.' }
    $resticCommands = @(Get-Command -Name $ResticExe -CommandType Application -ErrorAction Stop)
    $sshCommands = @(Get-Command -Name 'ssh.exe' -CommandType Application -ErrorAction Stop)
    if ($resticCommands.Count -ne 1 -or $sshCommands.Count -ne 1) { throw 'A unique Restic and OpenSSH executable must be available.' }
    if ($null -eq $RepositoryPassword) {
        $RepositoryPassword = Read-Host 'Restic recovery password (keep a separate recovery copy)' -AsSecureString
        $ownsPassword = $true
    }
    if ($InitializeRepository) {
        $confirmation = Read-Host 'Confirm the new Restic recovery password' -AsSecureString
    }
    $result = Invoke-StagingBackupPull -SshTarget $SshTarget -IdentityFile $IdentityFile `
        -ResticExecutable $resticCommands[0].Source -SshExecutable $sshCommands[0].Source `
        -BackupRoot $BackupRoot -InitializeRepository $InitializeRepository.IsPresent `
        -VerifyRoundTrip $VerifyRoundTrip.IsPresent `
        -Password $RepositoryPassword -ConfirmationPassword $confirmation
    $result | ConvertTo-Json -Depth 5 -Compress
}
catch {
    # Exception messages from this script are fixed diagnostics; do not include
    # child stdout/stderr, process arguments or password material in logs.
    [pscustomobject]@{ status = 'error'; message = $_.Exception.Message } | ConvertTo-Json -Compress
    exit 1
}
finally {
    if ($null -ne $confirmation) { $confirmation.Dispose() }
    if ($ownsPassword -and $null -ne $RepositoryPassword) { $RepositoryPassword.Dispose() }
}
