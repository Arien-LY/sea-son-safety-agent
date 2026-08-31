[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Repository,
    [string]$Branch = "main",
    [switch]$KeepClone
)

$ErrorActionPreference = "Stop"
$TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd('\')
$CloneName = "sea-son-clean-clone-" + [guid]::NewGuid().ToString("N")
$CloneRoot = [System.IO.Path]::GetFullPath((Join-Path $TempRoot $CloneName))
$ExpectedPrefix = $TempRoot + [System.IO.Path]::DirectorySeparatorChar
$Succeeded = $false

if (-not $CloneRoot.StartsWith($ExpectedPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
    -not ([System.IO.Path]::GetFileName($CloneRoot)).StartsWith("sea-son-clean-clone-")) {
    throw "Refusing to use an unverified temporary clone path."
}

try {
    & git clone --no-tags --single-branch --branch $Branch $Repository $CloneRoot
    if ($LASTEXITCODE -ne 0) { throw "Clean clone failed." }

    if (Test-Path -LiteralPath (Join-Path $CloneRoot ".env")) {
        throw "A local .env unexpectedly appeared in the clean clone."
    }
    if (Test-Path -LiteralPath (Join-Path $CloneRoot "uploads")) {
        throw "Runtime uploads unexpectedly appeared in the clean clone."
    }
    $RuntimeData = @(Get-ChildItem -LiteralPath (Join-Path $CloneRoot "data") -Filter "*.json" -File)
    if ($RuntimeData.Count -ne 0) {
        throw "Runtime data JSON unexpectedly appeared in the clean clone."
    }

    & powershell -ExecutionPolicy Bypass -File (Join-Path $CloneRoot "scripts\setup.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Clean-clone setup failed." }
    & powershell -ExecutionPolicy Bypass -File (Join-Path $CloneRoot "scripts\verify.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Clean-clone verification failed." }

    $Commit = (& git -C $CloneRoot rev-parse HEAD).Trim()
    $Succeeded = $true
    [pscustomobject]@{
        schema_version = "phase6-clean-clone-result-v1"
        repository = $Repository
        branch = $Branch
        commit = $Commit
        env_copied = $false
        runtime_data_copied = $false
        setup_passed = $true
        verify_passed = $true
        clone_kept = [bool]$KeepClone
    } | ConvertTo-Json
}
finally {
    if ($Succeeded -and -not $KeepClone -and (Test-Path -LiteralPath $CloneRoot)) {
        $Resolved = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $CloneRoot).Path)
        if ($Resolved.StartsWith($ExpectedPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
            ([System.IO.Path]::GetFileName($Resolved)).StartsWith("sea-son-clean-clone-")) {
            Remove-Item -LiteralPath $Resolved -Recurse -Force
        }
        else {
            throw "Refusing to remove an unverified clone path."
        }
    }
    elseif ((Test-Path -LiteralPath $CloneRoot) -and ($KeepClone -or -not $Succeeded)) {
        Write-Warning "Clean clone retained for inspection: $CloneRoot"
    }
}
