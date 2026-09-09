# Build both one-file packages: Windows (native) and Linux (Docker).
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$Version = python -c "from fh6parse._version import __version__; print(__version__)"
if (-not $Version) { throw "could not read package version" }

Write-Host "==> Windows one-file (v$Version)"
& (Join-Path $PSScriptRoot "build_windows.bat")
if ($LASTEXITCODE -ne 0) { throw "Windows build failed" }

Write-Host "==> Linux one-file (Docker)"
& (Join-Path $PSScriptRoot "build_linux_docker.ps1")

Write-Host "==> Versioned packages"
New-Item -ItemType Directory -Force -Path "dist\packages" | Out-Null
Copy-Item -Force "packaging\USAGE.txt" "dist\packages\USAGE.txt"

$winName = "fh6parse-$Version-windows-x64"
$linName = "fh6parse-$Version-linux-x86_64"
Copy-Item -Force "dist\windows\fh6parse.exe" "dist\packages\$winName.exe"

$absLinux = (Resolve-Path "dist\linux").Path
$absOut = (Resolve-Path "dist\packages").Path
docker run --rm -v "${absLinux}:/in:ro" -v "${absOut}:/out" ubuntu:22.04 bash -lc @"
cp /in/fh6parse /out/$linName
chmod 755 /out/$linName
tar -C /out -czf /out/$linName.tar.gz $linName
"@

$zip = Join-Path $absOut "$winName.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "dist\packages\$winName.exe" -DestinationPath $zip

Get-ChildItem "dist\packages" | Format-Table Name, Length
Write-Host "Done. v$Version"
