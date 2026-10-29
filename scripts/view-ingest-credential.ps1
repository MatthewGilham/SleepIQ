param([switch]$Show)
$ErrorActionPreference = 'Stop'
if (!$Show) { throw 'Private local display requires explicit -Show; never print credentials into a terminal or chat.' }
. (Join-Path $PSScriptRoot 'private-folders.ps1')
. (Join-Path $PSScriptRoot 'credential-dialog.ps1')
$dataRoot = Join-Path $env:LOCALAPPDATA 'SleepIQ'
$security = Join-Path $dataRoot 'security'
Assert-PrivateFolder $dataRoot
Assert-PrivateFolder $security
$file = Get-Item -LiteralPath (Join-Path $security 'ingest-token.dpapi') -ErrorAction Stop
if ($file.PSIsContainer -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'A regular local credential file is required.'
}
$protected = Get-Content -Raw -LiteralPath $file.FullName | ConvertTo-SecureString
$pointer = [IntPtr]::Zero
$token = $null
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($protected)
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    Show-IngestCredential $token
} finally {
    $token = $null
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}
