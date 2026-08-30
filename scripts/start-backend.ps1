$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Virtual environment not found. Run .\scripts\setup.ps1 first."
}
Set-Location $ProjectRoot
$BackendArgs = @('-m', 'uvicorn', 'backend.app.main:app', '--reload', '--host', '127.0.0.1', '--port', '8000')
if (Test-Path -LiteralPath (Join-Path $ProjectRoot '.env')) {
    $BackendArgs += @('--env-file', (Join-Path $ProjectRoot '.env'))
}
& $PythonExe @BackendArgs
