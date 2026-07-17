$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment not found. Run .\scripts\setup.ps1 first."
}

& $python -m src.chaos.cards.cli @args
exit $LASTEXITCODE
