$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}

Set-Location $ProjectRoot
& $PythonExe -m pytest
if ($LASTEXITCODE -ne 0) {
    throw "Python tests failed."
}

Push-Location (Join-Path $ProjectRoot "frontend")
try {
    & npm.cmd test
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend behavior tests failed."
    }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend build failed."
    }
}
finally {
    Pop-Location
}
