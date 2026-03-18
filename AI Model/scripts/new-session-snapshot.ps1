param(
  [string]$Blockers,
  [string[]]$NextActions
)
$state = "$(Split-Path $PSScriptRoot -Parent)\.agent\SESSION_STATE.md"
$today = Get-Date -Format "yyyy-MM-dd"
$lines = @()
$lines += "# Session State"
$lines += ""
$lines += "Date: $today"
$lines += "Blockers:"
$lines += $Blockers.Split("`n") | ForEach-Object { "- $_" }
$lines += ""
$lines += "Next 3 actions:"
if ($NextActions) { foreach ($a in $NextActions) { $lines += "- $a" } }
Set-Content -Path $state -Value $lines
