<#
  Crea el programa de Windows de Kreix.

    powershell -ExecutionPolicy Bypass -File packaging\build.ps1

  1. Prepara un entorno aparte (.venv-build) con las dependencias y PyInstaller.
  2. Empaqueta Kreix en dist\Kreix\Kreix.exe y comprueba que el programa empaquetado arranca y recorre todas las paginas.
  3. Si encuentra Inno Setup 6, crea el instalador dist\Kreix-Setup-<version>.exe (acceso directo en Inicio y en el
     escritorio, sin permisos de administrador). Si no, deja un .zip portatil.
#>
param([switch]$SkipInstaller)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (Select-String -Path "ui\whats_new.py" -Pattern 'VERSION = "([\d.]+)"').Matches[0].Groups[1].Value
Write-Host "Kreix $version"

if (-not (Test-Path ".venv-build\Scripts\python.exe")) {
    Write-Host "Creando el entorno de compilacion..."
    py -3 -m venv .venv-build
}
& ".venv-build\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }

Write-Host "Empaquetando..."
& ".venv-build\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\kreix.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo." }

Write-Host "Comprobando el programa empaquetado..."
$report = Join-Path $env:TEMP "kreix-selftest.txt"
Remove-Item $report -ErrorAction SilentlyContinue
$env:QT_QPA_PLATFORM = "offscreen"
$process = Start-Process -FilePath "dist\Kreix\Kreix.exe" -ArgumentList "--selftest", "`"$report`"" -Wait -PassThru
Remove-Item Env:\QT_QPA_PLATFORM
if (-not (Test-Path $report) -or (Get-Content $report -Raw).Trim() -ne "OK") {
    if (Test-Path $report) { Get-Content $report }
    throw "El programa empaquetado no supero la comprobacion."
}
Write-Host "El programa empaquetado funciona."

if ($SkipInstaller) { return }

$candidates = @(@(
    $env:ISCC,
    (Join-Path $root "packaging\tools\InnoSetup\ISCC.exe"),
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) })

if ($candidates) {
    Write-Host "Creando el instalador..."
    & $candidates[0] "/DAppVersion=$version" "packaging\installer.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup fallo." }
    Write-Host "Listo: dist\Kreix-Setup-$version.exe"
} else {
    $zip = "dist\Kreix-$version-portatil.zip"
    Remove-Item $zip -ErrorAction SilentlyContinue
    Compress-Archive -Path "dist\Kreix" -DestinationPath $zip
    Write-Host "No se encontro Inno Setup 6 (https://jrsoftware.org/isdl.php): se deja un .zip portatil en $zip"
}
