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
$Stamp = python -c "from fh6parse._version import package_stamp; print(package_stamp())"
if (-not $Version) { throw "could not read package version" }
if (-not $Stamp) { throw "could not read package stamp" }

$stamped = Join-Path $Root "dist\packages\fh6parse-$Stamp-windows-x64.exe"
$plain = Join-Path $Root "dist\packages\fh6parse-$Version-windows-x64.exe"
if (-not (Test-Path $stamped)) {
    throw "missing $stamped - run packaging\build_windows.bat first"
}
if (-not (Test-Path $plain)) {
    Copy-Item -Force $stamped $plain
}

$uploads = @($stamped)
if ((Resolve-Path $stamped).Path -ne (Resolve-Path $plain).Path) {
    $uploads += $plain
}

$tag = "v$Version"
$notes = "Windows office GUI $Stamp. Yellow UPDATE to … bar under the mill/print row: one click downloads this exe and restarts. Keep fh6parse-kiosk.ini next to the exe (STEP folders, language). Mill table is %USERPROFILE%\.config\fh6parse\machines.ini."

gh --version | Out-Null
$exists = $false
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
gh release view $tag --repo Don-Pablo-G/fh6parse 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { $exists = $true }
$ErrorActionPreference = $prev

if ($exists) {
    Write-Host "Uploading to existing $tag"
    gh release upload $tag @uploads --clobber --repo Don-Pablo-G/fh6parse
} else {
    Write-Host "Creating $tag"
    gh release create $tag @uploads --title "fh6parse $Stamp" --notes $notes --repo Don-Pablo-G/fh6parse --target master
}

Write-Host "Published $($uploads -join ', ') as $tag"
Write-Host "Office PCs with an older exe show UPDATE to $Version after the next launch (network required)."
