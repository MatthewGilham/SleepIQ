param(
    [ValidateSet('Staging', 'Production')][string]$Environment = 'Staging',
    [int]$RenewDays = 30,
    [switch]$ForceRenewal,
    [switch]$AcceptTerms,
    [switch]$SkipReceiverRestart
)
# Renews the sync.mgilham.online certificate with the pinned lego tool (P25). Safe by construction:
#  * renewal happens in a private COPY of the ACME folder; the live certificate is untouched until the new one validates;
#  * the new certificate must match the hostname, be currently valid, expire later than the old one, and load with its key;
#  * the swap keeps the previous files, and a receiver that does not come back healthy is rolled back;
#  * output from lego is never printed or logged; only a result word is recorded.
# Staging produces an untrusted certificate: it is never copied into the Production live folder.
$ErrorActionPreference = 'Stop'
if (!$AcceptTerms) { throw 'Read the certificate authority terms before explicitly passing -AcceptTerms.' }
. (Join-Path $PSScriptRoot 'private-folders.ps1')
. (Join-Path $PSScriptRoot 'certificate-tools.ps1')
$root = Split-Path $PSScriptRoot -Parent
$executable = Join-Path $root '.tools/lego/5.5.2/lego.exe'
$python = Join-Path $root '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $executable)) { throw 'Install the checksum-verified Lego tool first.' }
$security = Join-Path $env:LOCALAPPDATA 'SleepIQ/security'
Assert-PrivateFolder $security
$live = Join-Path $security ('acme-' + $Environment.ToLowerInvariant())
Assert-PrivateFolder $live
$liveCertificates = Join-Path $live 'certificates'
Assert-PrivateFolder $liveCertificates
$names = @('sync.mgilham.online.crt', 'sync.mgilham.online.key', 'sync.mgilham.online.issuer.crt', 'sync.mgilham.online.json')
$certificate = Join-Path $liveCertificates $names[0]
$started = [DateTime]::UtcNow

function Complete([string]$Result, [string]$Message, [bool]$Failed) {
    if ($Environment -eq 'Production') {
        try { Write-CertificateStatus $security $certificate $Result $started } catch { }
    }
    Write-Output $Message
    # exit may skip the finally block, so the working copy (it holds a private key) is removed here too.
    if ($script:work -and (Test-Path -LiteralPath $script:work)) {
        Remove-Item -LiteralPath $script:work -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($Failed) { exit 1 }
    exit 0
}

$before = Get-CertificateInfo $certificate
if (!$ForceRenewal -and !(Test-RenewalDue $before.NotAfter $started $RenewDays)) {
    Complete 'not_due' ("Certificate valid until $(Format-UtcStamp $before.NotAfter); renewal is due within $RenewDays days. Nothing changed.") $false
}

# The ACME account email is the account folder's name, so it is never stored or typed again.
$accountParent = Join-Path $live 'accounts/acme-v02.api.letsencrypt.org'
if ($Environment -eq 'Staging') { $accountParent = Join-Path $live 'accounts/acme-staging-v02.api.letsencrypt.org' }
$account = Get-ChildItem -LiteralPath $accountParent -Directory | Select-Object -First 1
if (!$account) { Complete 'failed' 'Renewal failed: no ACME account found. Nothing changed.' $true }

$script:work = Join-Path $security ('acme-' + $Environment.ToLowerInvariant() + '-renew')
$tokenFile = Join-Path $security 'cloudflare-token.dpapi'
$pointer = [IntPtr]::Zero
$process = $null
$swapped = $false
try {
    if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
    New-Item -ItemType Directory -Path $work | Out-Null
    Assert-PrivateFolder $work
    Copy-Item -LiteralPath (Join-Path $live 'accounts') -Destination $work -Recurse
    Copy-Item -LiteralPath $liveCertificates -Destination $work -Recurse
    $protected = Get-Content -Raw -LiteralPath $tokenFile | ConvertTo-SecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($protected)
    $server = if ($Environment -eq 'Staging') { 'letsencrypt-staging' } else { 'letsencrypt' }
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $executable
    $force = if ($ForceRenewal) { ' --renew-force' } else { '' }
    $info.Arguments = "run --dns cloudflare --domains $script:CertificateHost --path `"$work`" --server $server --accept-tos --renew-days $RenewDays --no-random-sleep --log.level error$force"
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    foreach ($name in @($info.EnvironmentVariables.Keys)) {
        if ($name -match '^(CF_|CLOUDFLARE_|LEGO_)') { $info.EnvironmentVariables.Remove($name) }
    }
    $info.EnvironmentVariables['CF_DNS_API_TOKEN'] = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $info.EnvironmentVariables['CF_ZONE_API_TOKEN'] = $info.EnvironmentVariables['CF_DNS_API_TOKEN']
    $info.EnvironmentVariables['LEGO_EMAIL'] = $account.Name
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    $process.Start() | Out-Null
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (!$process.WaitForExit(600000)) {
        $process.Kill()
        $process.WaitForExit()
        Complete 'failed' 'Renewal timed out. The live certificate was not changed.' $true
    }
    $stdout.Wait(); $stderr.Wait()
    if ($process.ExitCode) { Complete 'failed' 'Renewal failed (tool output withheld). The live certificate was not changed.' $true }

    # Validate the candidate before it can replace anything.
    $candidatePath = Join-Path $work 'certificates'
    $candidate = Get-CertificateInfo (Join-Path $candidatePath $names[0])
    $now = [DateTime]::UtcNow
    if ($candidate.Hostname -ne $script:CertificateHost -or $candidate.NotBefore -gt $now -or $candidate.NotAfter -le $now.AddDays(1)) {
        Complete 'failed' 'New certificate failed the hostname/validity check. The live certificate was not changed.' $true
    }
    if ($candidate.NotAfter -le $before.NotAfter) {
        Complete 'not_due' 'The tool kept the existing certificate (not yet due). Nothing changed.' $false
    }
    & $python -I -c "import ssl,sys; c=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); c.load_cert_chain(sys.argv[1], sys.argv[2])" (Join-Path $candidatePath $names[0]) (Join-Path $candidatePath $names[1])
    if ($LASTEXITCODE) { Complete 'failed' 'New certificate and key do not load together. The live certificate was not changed.' $true }

    if ($Environment -eq 'Staging') {
        Complete 'staging_ok' ("STAGING renewal succeeded and validated (expires $(Format-UtcStamp $candidate.NotAfter)); it is untrusted and was NOT installed.") $false
    }

    # Swap: keep the previous files, stop the receiver, replace, restart, verify, roll back on failure.
    $previous = Join-Path $security 'acme-production-previous'
    if (Test-Path -LiteralPath $previous) { Remove-Item -LiteralPath $previous -Recurse -Force }
    New-Item -ItemType Directory -Path $previous | Out-Null
    Assert-PrivateFolder $previous
    foreach ($name in $names) { Copy-Item -LiteralPath (Join-Path $liveCertificates $name) -Destination $previous -Force }
    $taskName = 'SleepIQ receiver'
    $hasTask = !$SkipReceiverRestart -and (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)
    if ($hasTask) { Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue; Start-Sleep -Seconds 3 }
    foreach ($name in $names) { Copy-Item -LiteralPath (Join-Path $candidatePath $name) -Destination $liveCertificates -Force }
    $swapped = $true
    $healthy = $true
    if ($hasTask) {
        Start-ScheduledTask -TaskName $taskName
        $healthy = $false
        for ($i = 0; $i -lt 12 -and !$healthy; $i++) {
            Start-Sleep -Seconds 5
            try { $healthy = (Invoke-RestMethod -Uri "https://$script:CertificateHost`:8443/health" -TimeoutSec 5).status -eq 'ok' } catch { }
        }
    }
    if (!$healthy) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
        foreach ($name in $names) { Copy-Item -LiteralPath (Join-Path $previous $name) -Destination $liveCertificates -Force }
        Start-ScheduledTask -TaskName $taskName
        Complete 'rolled_back' 'The receiver was not healthy with the new certificate, so the previous certificate was restored.' $true
    }
    Complete 'renewed' ("Certificate renewed; now valid until $(Format-UtcStamp $candidate.NotAfter).") $false
} catch {
    Complete 'failed' 'Renewal failed unexpectedly (details withheld). Check the status with certificate-status.ps1.' $true
} finally {
    if ($process -ne $null) { $process.Dispose() }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    # The working copy holds a private key: always remove it.
    if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
}
