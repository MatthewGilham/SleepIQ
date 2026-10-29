# Helpers for the desktop launcher (L01). Dot-source. Talks only to the fixed loopback address.

function Get-SleepIQAddress([int]$Port) { "http://127.0.0.1:$Port" }

# True only if something on the port answers the SleepIQ health check with {"status":"ok"}.
function Test-SleepIQRunning([int]$Port) {
    try {
        $request = [Net.WebRequest]::Create("$(Get-SleepIQAddress $Port)/api/v1/health")
        $request.Timeout = 2000
        $request.Proxy = $null
        $response = $request.GetResponse()
        try {
            $reader = New-Object IO.StreamReader($response.GetResponseStream())
            try { return (($reader.ReadToEnd() | ConvertFrom-Json).status -eq 'ok') } finally { $reader.Dispose() }
        } finally { $response.Dispose() }
    } catch { return $false }
}

function Wait-SleepIQReady([int]$Port, [int]$TimeoutSeconds) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-SleepIQRunning $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

# Chrome if Windows lists it, otherwise the default browser. Only the fixed local address is ever opened.
# SLEEPIQ_TEST_BROWSER_LOG is a test hook: when set, the address is appended to that file instead.
function Open-SleepIQBrowser([int]$Port) {
    $address = Get-SleepIQAddress $Port
    if ($env:SLEEPIQ_TEST_BROWSER_LOG) { Add-Content -LiteralPath $env:SLEEPIQ_TEST_BROWSER_LOG -Value $address; return }
    $chrome = $null
    foreach ($key in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe',
                       'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe')) {
        $path = (Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue).'(default)'
        if ($path -and (Test-Path -LiteralPath $path)) { $chrome = $path; break }
    }
    if ($chrome) { Start-Process -FilePath $chrome -ArgumentList $address } else { Start-Process $address }
}
