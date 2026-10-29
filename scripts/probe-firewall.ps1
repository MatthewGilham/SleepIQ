param([ValidateSet('Preview', 'Add', 'Remove')][string]$Mode = 'Preview')
$ErrorActionPreference = 'Stop'
$ruleName = 'SleepIQ-Synthetic-HTTPS-8443'
if ($Mode -eq 'Remove') {
    # Delete only this explicitly named rule; no wildcard or profile-policy changes.
    Remove-NetFirewallRule -Name $ruleName -ErrorAction Stop
    Write-Output 'SleepIQ synthetic HTTPS rule removed.'
    return
}
. (Join-Path $PSScriptRoot 'probe-network.ps1')
$interface = Get-ProbeNetwork
$python = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Project Python not found.' }
$rule = @{
    Name = $ruleName
    DisplayName = 'SleepIQ synthetic HTTPS (home only)'
    Direction = 'Inbound'
    Action = 'Allow'
    Enabled = 'True'
    Profile = 'Private'
    Protocol = 'TCP'
    LocalAddress = '192.168.1.190'
    LocalPort = 8443
    RemoteAddress = '192.168.1.0/24'
    InterfaceAlias = $interface
    Program = $python
    EdgeTraversalPolicy = 'Block'
}
if ($Mode -eq 'Preview') {
    [pscustomobject]$rule | Format-List
    Write-Output 'Preview only; no firewall change made.'
    return
}
if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) {
    throw 'Named rule already exists; inspect it rather than replacing it.'
}
New-NetFirewallRule @rule | Out-Null
Write-Output 'Only the named SleepIQ synthetic HTTPS rule was added. No server started.'
