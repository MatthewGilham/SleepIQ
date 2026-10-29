param(
    [switch]$Replace,
    [switch]$Remove,
    [string]$Folder = [Environment]::GetFolderPath('Desktop')   # -Folder exists so tests never touch your Desktop
)
# Creates (or removes) the SleepIQ desktop shortcut (L01). No admin rights, no autostart, no execution-policy change.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$link = Join-Path $Folder 'SleepIQ.lnk'
if ($Remove) {
    if (Test-Path -LiteralPath $link) { Remove-Item -LiteralPath $link; Write-Output 'Shortcut removed.' }
    else { Write-Output 'No shortcut to remove.' }
    return
}
if ((Test-Path -LiteralPath $link) -and !$Replace) { throw "A shortcut already exists at $link. Use -Replace to overwrite it." }
if (!(Test-Path -LiteralPath $Folder)) { throw "Folder not found: $Folder" }
$shell = New-Object -ComObject WScript.Shell
try {
    $shortcut = $shell.CreateShortcut($link)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments = "-NoProfile -File `"$(Join-Path $root 'scripts\launch.ps1')`""
    $shortcut.WorkingDirectory = $root
    $shortcut.WindowStyle = 1
    $shortcut.IconLocation = (Join-Path $env:SystemRoot 'System32\shell32.dll') + ',14'
    $shortcut.Description = 'Start SleepIQ and open it in your browser. Close the window to stop it.'
    $shortcut.Save()
} finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell) }
Write-Output "Shortcut created: $link"
