$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EntryPoint = Join-Path $ProjectRoot "main_debug.py"

$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
$IsAdmin = $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $IsAdmin) {
    $Process = Start-Process `
        -FilePath $Python `
        -ArgumentList @($EntryPoint) `
        -WorkingDirectory $ProjectRoot `
        -Verb RunAs `
        -WindowStyle Hidden `
        -PassThru
    Write-Output "Elevated ok-chaos started with PID $($Process.Id)."
    exit 0
}

$ExistingApps = Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -like "ok-chaos *" }
foreach ($ExistingApp in $ExistingApps) {
    Stop-Process -Id $ExistingApp.Id -Force
}

Push-Location $ProjectRoot
try {
    & $Python $EntryPoint
}
finally {
    Pop-Location
}
