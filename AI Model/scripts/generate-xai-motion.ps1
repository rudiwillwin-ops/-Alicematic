param(
  [switch]$Execute,
  [int]$MaxClips = 3,
  [int]$Duration = 10,
  [string]$Resolution = "720p",
  [int]$StitchEvery = 3
)
$cmd = "python automation/scripts/generate_xai_imagine_videos.py --max-clips $MaxClips --duration $Duration --resolution $Resolution --stitch-every $StitchEvery"
if ($Execute) { $cmd += " --execute" }
Write-Host $cmd
Invoke-Expression $cmd
