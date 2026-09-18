# Publish the Windows one-file exe as a GitHub Release so office PCs can UPDATE.
# Prefer: bump version, git tag vX.Y.Z, push the tag — GitHub Actions builds and
# publishes. This script is the local fallback (needs PyInstaller + gh).
# Build first: packaging\build_windows.bat
# Then: gh auth login   (once)
#       powershell -File packaging\publish_windows.ps1
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$Version = python -c "from fh6parse._version import __version__; print(__version__)"
if (-not $Version) { throw "could not read package version" }

$exe = Join-Path $Root "dist\packages\fh6parse-$Version-windows-x64.exe"
if (-not (Test-Path $exe)) {
    throw "missing $exe - run packaging\build_windows.bat first"
}

$tag = "v$Version"
$notes = "Windows office GUI. On the PC: yellow UPDATE downloads this exe and restarts. Keep fh6parse-kiosk.ini next to the exe (STEP folders, language)."

gh --version | Out-Null
$exists = $false
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
gh release view $tag --repo Don-Pablo-G/fh6parse 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { $exists = $true }
$ErrorActionPreference = $prev

if ($exists) {
    Write-Host "Uploading to existing $tag"
    gh release upload $tag $exe --clobber --repo Don-Pablo-G/fh6parse
} else {
    Write-Host "Creating $tag"
    gh release create $tag $exe --title "fh6parse $Version" --notes $notes --repo Don-Pablo-G/fh6parse --target master
}

Write-Host "Published $exe as $tag"
Write-Host "Office PCs with an older exe show UPDATE to $Version after the next launch (network required)."
