$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Version = & $Python -c "from src.version import __version__; print(__version__)"
$Name = "ok-chaos-win32-portable-v$Version"

Push-Location $ProjectRoot
try {
    $Arguments = @(
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--uac-admin",
        "--name", $Name,
        "--paths", $ProjectRoot,
        "--hidden-import", "src.tasks.ChaosTask",
        "--collect-submodules", "ok",
        "--collect-all", "onnxocr",
        "--collect-all", "openvino",
        "--collect-all", "opencc",
        "--collect-all", "pyappify",
        "--add-data", "$ProjectRoot\data\cards;data/cards",
        "--add-data", "$ProjectRoot\datasets\cards\reference\haide_mali\flash_layers.pending.json;datasets/cards/reference/haide_mali",
        "--add-data", "$ProjectRoot\datasets\cards\review\haide_mali\epiphany.pending.json;datasets/cards/review/haide_mali",
        (Join-Path $ProjectRoot "main.py")
    )
    & $Python -m PyInstaller @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Host "Built: $(Join-Path $ProjectRoot "dist\$Name.exe")"
