param(
  [string]$SkillSource = "$PSScriptRoot\..",
  [string]$PersonalSkillsRoot = "$HOME\.cursor\skills"
)

$dest = Join-Path $PersonalSkillsRoot "doc-first-workflow"

New-Item -ItemType Directory -Force -Path $PersonalSkillsRoot | Out-Null

if (Test-Path $dest) {
  Remove-Item -Recurse -Force $dest
}

Copy-Item -Recurse -Force $SkillSource $dest

Write-Host "Installed doc-first-workflow to: $dest"

