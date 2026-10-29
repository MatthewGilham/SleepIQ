param([Parameter(Mandatory = $true)][ValidateSet('Install', 'Remove', 'Run', 'Status')][string]$Action)
# Owner-run, per-user scheduled task that renews the production certificate when 30 days or fewer remain (P25).
# Runs at YOUR logon (hidden, no admin rights, no service). Install only after a successful staging dry run.
$ErrorActionPreference = 'Stop'
$taskName = 'SleepIQ certificate renewal'
$root = Split-Path $PSScriptRoot -Parent
function Get-RenewalTask { Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue }

switch ($Action) {
    'Install' {
        if (Get-RenewalTask) { throw "Task '$taskName' already exists. Remove it first." }
        $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        $shell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $script = Join-Path $root 'scripts\renew-certificate.ps1'
        $arguments = "-NoProfile -WindowStyle Hidden -File `"$script`" -Environment Production -AcceptTerms"
        $taskAction = New-ScheduledTaskAction -Execute $shell -Argument $arguments -WorkingDirectory $root
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
        $trigger.Delay = 'PT5M'   # after the receiver (1 minute) and Wi-Fi are up
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
        $null = Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $trigger `
            -Settings $settings -Principal $principal `
            -Description 'Renews the SleepIQ sync certificate when 30 days or fewer remain. Remove with renewal-task.ps1 -Action Remove.'
        Write-Output 'Installed. It runs 5 minutes after each of your logons and does nothing unless renewal is due.'
    }
    'Remove' {
        if (!(Get-RenewalTask)) { Write-Output 'Task is not installed.'; return }
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Output 'Task removed. Certificates will no longer renew automatically.'
    }
    'Run' {
        if (!(Get-RenewalTask)) { throw 'Task is not installed.' }
        Start-ScheduledTask -TaskName $taskName
        Write-Output 'Run requested. Check with -Action Status in a minute or two.'
    }
    'Status' {
        $task = Get-RenewalTask
        Write-Output $(if ($task) { "Task state: $($task.State)" } else { 'Task: not installed' })
        if ($task) {
            $info = Get-ScheduledTaskInfo -TaskName $taskName
            Write-Output "Last run result: $($info.LastTaskResult) (0 = fine)"
        }
        $status = Join-Path $env:LOCALAPPDATA 'SleepIQ/security/certificate-status.json'
        if (Test-Path -LiteralPath $status) {
            $s = Get-Content -Raw -LiteralPath $status | ConvertFrom-Json
            $days = [math]::Floor(([datetime]::Parse($s.not_after_utc).ToUniversalTime() - [DateTime]::UtcNow).TotalDays)
            Write-Output "Certificate expires: $($s.not_after_utc) ($days days). Last renewal attempt: $($s.last_result) $($s.last_attempt_utc)"
        } else { Write-Output 'No certificate status recorded yet.' }
    }
}
