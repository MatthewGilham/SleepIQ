$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'private-folders.ps1')
. (Join-Path $PSScriptRoot 'probe-network.ps1')
. (Join-Path $PSScriptRoot 'probe-checks.ps1')
$null = Get-ProbeNetwork
$security = Join-Path $env:LOCALAPPDATA 'SleepIQ/security'
Assert-PrivateFolder $security
$protected = Get-Content -Raw -LiteralPath (Join-Path $security 'ingest-token.dpapi') | ConvertTo-SecureString
$pointer = [IntPtr]::Zero
$token = $null
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($protected)
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    Test-ProbeRequests $token
} finally {
    $token = $null
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}
Write-Output 'Synthetic HTTPS checks passed from this PC. No health data sent or stored. Phone/exporter POST tests remain separate.'
