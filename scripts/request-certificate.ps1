param(
    [ValidateSet('Staging', 'Production')][string]$Environment = 'Staging',
    [Parameter(Mandatory = $true)][string]$Email,
    [switch]$AcceptTerms
)
$ErrorActionPreference = 'Stop'
if (!$AcceptTerms) { throw 'Read the certificate authority terms before explicitly passing -AcceptTerms.' }
. (Join-Path $PSScriptRoot 'private-folders.ps1')
$root = Split-Path $PSScriptRoot -Parent
$executable = Join-Path $root '.tools/lego/5.5.2/lego.exe'
if (!(Test-Path -LiteralPath $executable)) { throw 'Install the checksum-verified Lego tool first.' }
$security = Join-Path $env:LOCALAPPDATA 'SleepIQ/security'
Assert-PrivateFolder $security
$tokenFile = Join-Path $security 'cloudflare-token.dpapi'
$protected = Get-Content -Raw -LiteralPath $tokenFile | ConvertTo-SecureString
$accountFolder = Join-Path $security ('acme-' + $Environment.ToLowerInvariant())
if (!(Test-Path -LiteralPath $accountFolder)) { New-Item -ItemType Directory -Path $accountFolder | Out-Null }
Assert-PrivateFolder $accountFolder
$pointer = [IntPtr]::Zero
$process = $null
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($protected)
    $server = if ($Environment -eq 'Staging') { 'letsencrypt-staging' } else { 'letsencrypt' }
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $executable
    # accountFolder is a Windows directory ending in a fixed component, not user-supplied shell text.
    $info.Arguments = "run --dns cloudflare --domains sync.mgilham.online --path `"$accountFolder`" --server $server --accept-tos --log.level error"
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    # Prevent inherited global keys, provider URLs or validation overrides from broadening this request.
    foreach ($name in @($info.EnvironmentVariables.Keys)) {
        if ($name -match '^(CF_|CLOUDFLARE_|LEGO_)') { $info.EnvironmentVariables.Remove($name) }
    }
    $info.EnvironmentVariables['CF_DNS_API_TOKEN'] = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $info.EnvironmentVariables['CF_ZONE_API_TOKEN'] = $info.EnvironmentVariables['CF_DNS_API_TOKEN']
    $info.EnvironmentVariables['LEGO_EMAIL'] = $Email
    # Proxy/network settings are preserved; these scripts do not evade session restrictions.
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    $process.Start() | Out-Null
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (!$process.WaitForExit(180000)) {
        $process.Kill()
        $process.WaitForExit()
        throw 'Certificate request timed out; no third-party output printed.'
    }
    $stdout.Wait()
    $stderr.Wait()
    if ($process.ExitCode) { throw 'Certificate request failed. Tool output withheld; review connectivity/token permissions locally.' }
    Write-Output "$Environment certificate request completed. No listener or firewall rule was enabled."
} finally {
    if ($process -ne $null) { $process.Dispose() }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}
