# Build a Windows installer from dist\ShotTrainer using Inno Setup.
#
# Requires Inno Setup 6+ on PATH (or pass -InnoSetupPath).
# After running, the installer lands at dist\ShotTrainer-Setup.exe.
#
# Run from the repo root:
#   pwsh packaging\make_installer.ps1
#
# Or pass an explicit Inno Setup compiler:
#   pwsh packaging\make_installer.ps1 -InnoSetupPath "C:\Program Files (x86)\Inno Setup 6\iscc.exe"

[CmdletBinding()]
param(
    [string]$InnoSetupPath = "iscc"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$bundle = Join-Path $repoRoot "dist\ShotTrainer"
$iss = Join-Path $PSScriptRoot "shottrainer.iss"

if (-not (Test-Path $bundle)) {
    Write-Error "$bundle not found. Run 'make package' first."
}

# Resolve iscc; if the caller didn't pass an explicit path, pick the
# default install location when 'iscc' isn't already on PATH.
$resolved = Get-Command $InnoSetupPath -ErrorAction SilentlyContinue
if (-not $resolved) {
    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $found) {
        Write-Error "Could not find Inno Setup compiler (iscc). Install Inno Setup 6 or pass -InnoSetupPath."
    }
    $InnoSetupPath = $found
}

& $InnoSetupPath $iss
if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup compiler exited with code $LASTEXITCODE"
}

$out = Join-Path $repoRoot "dist\ShotTrainer-Setup.exe"
Write-Host "Wrote $out"
