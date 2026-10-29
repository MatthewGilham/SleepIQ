param(
    [int]$Port = 8765,
    [int]$ReadyTimeoutSeconds = 60,
    [string]$StartScript = (Join-Path $PSScriptRoot 'start.ps1'),
    [switch]$NoPause
)
# What the desktop shortcut runs (L01, A5): start SleepIQ if needed, then open it in the browser.
# The window IS the app: closing it or pressing Ctrl+C stops SleepIQ. A second click never starts a second copy.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'launcher-tools.ps1')
$exitCode = 0
$helper = $null
try {
    if (Test-SleepIQRunning $Port) {
        Write-Output 'SleepIQ is already running. Opening it in your browser.'
        Open-SleepIQBrowser $Port
        return
    }
    $Host.UI.RawUI.WindowTitle = 'SleepIQ - keep this window open'
    Write-Output 'Starting SleepIQ. Keep this window open; close it or press Ctrl+C to stop SleepIQ.'
    # The browser opens only after the app answers, so it never shows a connection error.
    $helper = Start-Job -ArgumentList $PSScriptRoot, $Port, $ReadyTimeoutSeconds, $env:SLEEPIQ_TEST_BROWSER_LOG -ScriptBlock {
        param($scripts, $port, $timeout, $testLog)
        $env:SLEEPIQ_TEST_BROWSER_LOG = $testLog
        . (Join-Path $scripts 'launcher-tools.ps1')
        if (Wait-SleepIQReady $port $timeout) { Open-SleepIQBrowser $port }
    }
    & $StartScript
} catch {
    Write-Output "SleepIQ could not start: $($_.Exception.Message)"
    $exitCode = 1
} finally {
    if ($helper) { Stop-Job $helper -ErrorAction SilentlyContinue; Remove-Job $helper -Force -ErrorAction SilentlyContinue }
}
if ($exitCode -and !$NoPause) {
    Write-Output 'Press any key to close this window.'
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
}
exit $exitCode
