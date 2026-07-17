$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    py -3.12 -m venv (Join-Path $ProjectRoot ".venv")
}

& $VenvPython -m pip install --upgrade pip --timeout 180 --retries 5
& $VenvPython -m pip install "setuptools>=75" wheel --timeout 180 --retries 5
& $VenvPython -m pip install --no-build-isolation -e "${ProjectRoot}[dev]" --timeout 180 --retries 5
