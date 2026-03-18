param(
  [string]$PersonaFile,
  [switch]$Execute
)
$cmd = "python automation/scripts/bootstrap_persona.py --persona-file `"$PersonaFile`""
if ($Execute) { $cmd += " --execute" }
Write-Host $cmd
Invoke-Expression $cmd
