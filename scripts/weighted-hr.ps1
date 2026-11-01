param(
    [Parameter(Mandatory = $true)][ValidateSet('Prepare', 'Activate', 'Rollback', 'Status')][string]$Action,
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'SleepIQ'),
    [string]$BackupRoot = 'C:\Users\Matth\SleepIQ-Backups',
    [switch]$ConfirmIndividualHR,
    [string]$ReviewToken = ''
)
# Owner-run only. Stop the dashboard and receiver before mutation; never changes networking/trust.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'private-folders.ps1')
foreach ($folder in @($DataRoot, $BackupRoot, (Join-Path $DataRoot 'raw'))) { Assert-PrivateFolder $folder }
if ($Action -ne 'Status') {
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $_.LocalPort -in @(8765, 8443) })
    if ($listeners.Count) { throw 'Close SleepIQ and stop the receiver before changing HR calculations. See docs/OPERATIONS.md.' }
}
$previousPythonPath = $env:PYTHONPATH
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $env:PYTHONPATH = Join-Path (Get-Location) 'backend'
    $rolloutArgs = @($Action.ToLowerInvariant(), '--data-root', $DataRoot, '--backups', $BackupRoot)
    if ($ConfirmIndividualHR) { $rolloutArgs += '--confirm-individual-hr' }
    if ($ReviewToken) { $rolloutArgs += @('--review-token', $ReviewToken) }
    & .\.venv\Scripts\python.exe -m app.domain.rollout @rolloutArgs
    if ($LASTEXITCODE) { throw 'Weighted HR command failed; no activation is reported. Review locally before retrying.' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
