$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}
Set-Location $ProjectRoot
& $PythonExe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

