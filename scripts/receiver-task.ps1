param([Parameter(Mandatory = $true)][ValidateSet('Install', 'Remove', 'Start', 'Stop', 'Status')][string]$Action)
# Owner-run, per-user scheduled task for the always-on receiver (P20). No admin rights, no service.
# Starts the approved receiver at YOUR logon, hidden, with restart on failure. The dashboard stays manual.
$ErrorActionPreference = 'Stop'
$taskName = 'SleepIQ receiver'
$root = Split-Path $PSScriptRoot -Parent

function Get-ReceiverTask { Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue }

switch ($Action) {
    'Install' {
        if (Get-ReceiverTask) { throw "Task '$taskName' already exists. Remove it first." }
        $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        $shell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $script = Join-Path $root 'scripts\start-probe.ps1'
        $arguments = "-NoProfile -WindowStyle Hidden -File `"$script`" -Activate -EnableIngest"
        $taskAction = New-ScheduledTaskAction -Execute $shell -Argument $arguments -WorkingDirectory $root
        # Delay lets Wi-Fi connect first; the launcher itself re-checks address, profile and DNS.
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
        $trigger.Delay = 'PT1M'
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 10 `
            -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
        $null = Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $trigger `
            -Settings $settings -Principal $principal `
            -Description 'SleepIQ authenticated HTTPS receiver (home network only). Remove with receiver-task.ps1 -Action Remove.'
        Write-Output "Installed. It starts at your next logon; run -Action Start to start it now."
    }
    'Remove' {
        if (!(Get-ReceiverTask)) { Write-Output 'Task is not installed.'; return }
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Output 'Task removed. The receiver will no longer start automatically.'
    }
    'Start' {
        if (!(Get-ReceiverTask)) { throw 'Task is not installed.' }
        Start-ScheduledTask -TaskName $taskName
        Write-Output 'Start requested. Check with -Action Status in about 20 seconds.'
    }
    'Stop' {
        if (!(Get-ReceiverTask)) { throw 'Task is not installed.' }
        Stop-ScheduledTask -TaskName $taskName
        Write-Output 'Receiver stopped. It starts again at your next logon (or with -Action Start).'
    }
    'Status' {
        $task = Get-ReceiverTask
        if (!$task) { Write-Output 'Task: not installed'; return }
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        Write-Output "Task state: $($task.State)"
        Write-Output "Last run result: $($info.LastTaskResult) (0 = fine; 267009 = still running)"
        try {
            $response = Invoke-RestMethod -Uri 'https://sync.mgilham.online:8443/health' -TimeoutSec 5
            Write-Output "Receiver health check: $($response.status)"
        } catch {
            Write-Output 'Receiver health check: not reachable'
        }
    }
}
