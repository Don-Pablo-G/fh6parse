# Build Windows (native) and Raspberry Pi kiosk (Docker ARM) one-file packages.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$Version = python -c "from fh6parse._version import __version__; print(__version__)"
if (-not $Version) { throw "could not read package version" }

Write-Host "==> Windows one-file (v$Version)"
& (Join-Path $PSScriptRoot "build_windows.bat")
if ($LASTEXITCODE -ne 0) { throw "Windows build failed" }

Write-Host "==> Raspberry Pi one-file (Docker ARM)"
& (Join-Path $PSScriptRoot "build_raspberry_docker.ps1")

Write-Host "==> Versioned packages"
New-Item -ItemType Directory -Force -Path "dist\packages" | Out-Null
Copy-Item -Force "packaging\USAGE.txt" "dist\packages\USAGE.txt"
Copy-Item -Force "packaging\LINUX-KIOSK.md" "dist\packages\LINUX-KIOSK.md"

$winName = "fh6parse-$Version-windows-x64"
Copy-Item -Force "dist\windows\fh6parse.exe" "dist\packages\$winName.exe"
$zip = Join-Path (Resolve-Path "dist\packages").Path "$winName.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "dist\packages\$winName.exe" -DestinationPath $zip

function Pack-Pi {
    param(
        [Parameter(Mandatory = $true)][string]$SrcDir,
        [Parameter(Mandatory = $true)][string]$ArchName
    )
    $bin = Join-Path $SrcDir "fh6parse"
    if (-not (Test-Path $bin)) { throw "missing $bin" }
    $stage = Join-Path "dist\packages" "_stage-$ArchName"
    if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    Copy-Item $bin (Join-Path $stage "fh6parse")
    Copy-Item "packaging\fh6parse-kiosk.ini.example" $stage
    Copy-Item "packaging\fh6parse-kiosk.service" $stage
    Copy-Item "packaging\LINUX-KIOSK.md" $stage
    Copy-Item "packaging\USAGE.txt" $stage
    $tarName = "fh6parse-$Version-raspberrypi-$ArchName.tar.gz"
    $absStage = (Resolve-Path $stage).Path
    $absOut = (Resolve-Path "dist\packages").Path
    tar -C $absStage -czf (Join-Path $absOut $tarName) .
    Remove-Item -Recurse -Force $stage
    Write-Host "Packaged dist\packages\$tarName"
}

Pack-Pi -SrcDir "dist\raspberry-armv7" -ArchName "armv7"
Pack-Pi -SrcDir "dist\raspberry-aarch64" -ArchName "aarch64"

Get-ChildItem "dist\packages" | Format-Table Name, Length
Write-Host "Done. v$Version"
