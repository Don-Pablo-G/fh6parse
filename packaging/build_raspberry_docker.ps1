# Build Raspberry Pi one-file binaries (armv7 + aarch64) via Docker buildx.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running. Start Docker Desktop and retry."
}

function Invoke-PiBuild {
    param(
        [Parameter(Mandatory = $true)][string]$Platform,
        [Parameter(Mandatory = $true)][string]$OutDir
    )
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    Write-Host "==> Raspberry $Platform -> $OutDir"
    docker buildx build `
        --platform $Platform `
        -f packaging/Dockerfile.raspberry `
        --output "type=local,dest=$OutDir" `
        .
    if ($LASTEXITCODE -ne 0) { throw "docker buildx failed for $Platform" }
    $bin = Join-Path $OutDir "fh6parse"
    if (-not (Test-Path $bin)) { throw "$bin was not created" }
    Write-Host "Built $bin"
}

# Pi 3 32-bit OS (recommended) and 64-bit Bookworm.
Invoke-PiBuild -Platform "linux/arm/v7" -OutDir "dist/raspberry-armv7"
Invoke-PiBuild -Platform "linux/arm64" -OutDir "dist/raspberry-aarch64"
