# Build the Linux one-file binary using Docker (from Windows or Linux).
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

New-Item -ItemType Directory -Force -Path "dist\linux" | Out-Null

docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running. Start Docker Desktop and retry."
}

docker build -f packaging/Dockerfile.linux -t fh6parse-linux-build .
if ($LASTEXITCODE -ne 0) { throw "docker build failed" }

$absLinux = (Resolve-Path "dist\linux").Path
docker run --rm -v "${absLinux}:/dist" fh6parse-linux-build
if ($LASTEXITCODE -ne 0) { throw "docker run failed" }

$bin = Join-Path $absLinux "fh6parse"
if (-not (Test-Path $bin)) { throw "dist\linux\fh6parse was not created" }
Write-Host "Built dist\linux\fh6parse"
