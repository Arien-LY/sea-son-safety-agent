$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Host "Creating Python 3.12 virtual environment..."
    & py -3.12 -m venv (Join-Path $ProjectRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Python 3.12 virtual environment."
    }
}

Write-Host "Installing backend and Hello-Agents dependencies..."
& $PythonExe -m pip install -r (Join-Path $ProjectRoot "backend\requirements-dev.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Backend dependency installation failed."
}

Write-Host "Installing deterministic frontend dependencies..."
Push-Location (Join-Path $ProjectRoot "frontend")
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend dependency installation failed."
    }
}
finally {
    Pop-Location
}

Write-Host "Setup complete."
