param([switch]$Activate, [switch]$EnableIngest)
$ErrorActionPreference = 'Stop'
if (!$Activate) { throw 'LAN activation requires owner approval and explicit -Activate.' }
. (Join-Path $PSScriptRoot 'private-folders.ps1')
. (Join-Path $PSScriptRoot 'probe-network.ps1')
$null = Get-ProbeNetwork
$root = Split-Path $PSScriptRoot -Parent
$security = Join-Path $env:LOCALAPPDATA 'SleepIQ/security'
Assert-PrivateFolder $security
Assert-PrivateFolder (Join-Path $security 'acme-production')
$certificates = Join-Path $security 'acme-production/certificates'
Assert-PrivateFolder $certificates
$cert = New-Object Security.Cryptography.X509Certificates.X509Certificate2((Join-Path $certificates 'sync.mgilham.online.crt'))
try {
    if ($cert.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::DnsName, $false) -ne 'sync.mgilham.online' -or
        $cert.NotBefore.ToUniversalTime() -gt [DateTime]::UtcNow -or
        $cert.NotAfter.ToUniversalTime() -le [DateTime]::UtcNow.AddDays(1)) {
        throw 'Production certificate hostname or validity check failed.'
    }
} finally { $cert.Dispose() }
$tokenPath = Join-Path $security 'ingest-token.dpapi'
if (!(Test-Path -LiteralPath $tokenPath)) {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    $value = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    $encrypted = ConvertFrom-SecureString (ConvertTo-SecureString $value -AsPlainText -Force)
    # Exclusive creation refuses concurrent overwrite. Never print the generated credential.
    $stream = [IO.File]::Open($tokenPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    $writer = New-Object IO.StreamWriter($stream)
    try { $writer.Write($encrypted) } finally { $writer.Dispose() }
    $value = $null
    [Array]::Clear($bytes, 0, $bytes.Length)
}
$protected = Get-Content -Raw -LiteralPath $tokenPath | ConvertTo-SecureString
$pointer = [IntPtr]::Zero
$oldToken = $env:SLEEPIQ_PROBE_TOKEN
$oldCertificates = $env:SLEEPIQ_PROBE_CERTIFICATES
$oldIngest = $env:SLEEPIQ_INGEST_DATA
$oldBackup = $env:SLEEPIQ_BACKUP_ROOT
$env:SLEEPIQ_BACKUP_ROOT = $null
$env:SLEEPIQ_INGEST_DATA = $null
if ($EnableIngest) {
    # Real health uploads are accepted ONLY with this explicit switch (P19). Store must be provisioned.
    $dataRoot = Join-Path $env:LOCALAPPDATA 'SleepIQ'
    Assert-PrivateFolder $dataRoot
    Assert-PrivateFolder (Join-Path $dataRoot 'raw')
    $backupRoot = 'C:\Users\Matth\SleepIQ-Backups'
    Assert-PrivateFolder $backupRoot
    $env:SLEEPIQ_INGEST_DATA = $dataRoot
    $env:SLEEPIQ_BACKUP_ROOT = $backupRoot
}
Push-Location (Join-Path $root 'backend')
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($protected)
    $env:SLEEPIQ_PROBE_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:SLEEPIQ_PROBE_CERTIFICATES = $certificates
    if ($EnableIngest) { Write-Output 'Starting HTTPS receiver WITH health ingestion enabled. Ctrl+C stops it. No dashboard routes.' }
    else { Write-Output 'Starting synthetic HTTPS probe. Ctrl+C stops it. No health imports or dashboard routes.' }
    & (Join-Path $root '.venv/Scripts/python.exe') -m app.transport.serve
    if ($LASTEXITCODE) { throw 'Probe did not finish cleanly; no plaintext fallback was started.' }
} finally {
    $env:SLEEPIQ_PROBE_TOKEN = $oldToken
    $env:SLEEPIQ_PROBE_CERTIFICATES = $oldCertificates
    $env:SLEEPIQ_INGEST_DATA = $oldIngest
    $env:SLEEPIQ_BACKUP_ROOT = $oldBackup
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    Pop-Location
}
