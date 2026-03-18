param(
  [string]$Summary,
  [string[]]$Evidence
)
$ledger = "$(Split-Path $PSScriptRoot -Parent)\ledger\ROLLING_LEDGER.md"
$today = Get-Date -Format "yyyyMMdd"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
$index = (Get-Content $ledger | Select-String -Pattern "^## L-$today-" | Measure-Object).Count + 1
$id = "L-$today-" + $index.ToString("000")
Add-Content $ledger "`n## $id"
Add-Content $ledger "Summary: $Summary"
Add-Content $ledger "Evidence:"
if ($Evidence) { foreach ($e in $Evidence) { Add-Content $ledger "- $e" } } else { Add-Content $ledger "- (none)" }
Add-Content $ledger "Logged: $stamp"
