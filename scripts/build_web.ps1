# Windows: build the web interface and copy it into the Python package.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\web"
if (-not (Test-Path node_modules)) { npm ci --no-audit --no-fund }
$env:BIBAIFILTER_BUILD_MODE = "static"
npx next build
Remove-Item -Recurse -Force "$Root\src\bibaifilter\_web" -ErrorAction SilentlyContinue
Copy-Item -Recurse out "$Root\src\bibaifilter\_web"
Write-Host "Web interface copied to src\bibaifilter\_web"
