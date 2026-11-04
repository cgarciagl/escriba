<#
.SYNOPSIS
    Compila y empaqueta Escriba en dist\Escriba.exe.
.DESCRIPTION
    Script de compilacion nativo para PowerShell:
    1. Cierra Escriba.exe si esta en ejecucion.
    2. Valida Python y dependencias.
    3. Compila con PyInstaller usando Escriba.spec.
    4. Inicia el nuevo ejecutable compilado.
#>
[CmdletBinding()]
param(
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Escriba - Build EXE (PowerShell)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 0. Cerrar proceso si esta en ejecucion
Write-Host "[0/4] Cerrando Escriba.exe si esta corriendo..." -ForegroundColor Yellow
$proc = Get-Process -Name "Escriba" -ErrorAction SilentlyContinue
if ($proc) {
    Stop-Process -Name "Escriba" -Force
    Start-Sleep -Milliseconds 1500
    Write-Host "Escriba.exe cerrado." -ForegroundColor Green
} else {
    Write-Host "Escriba.exe no estaba corriendo." -ForegroundColor DarkGray
}

# 1. Detectar comando de Python
$pythonCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} else {
    Write-Error "No se encontro 'py' ni 'python' en PATH. Instala Python para continuar."
    exit 1
}

# 2. Validar dependencias
Write-Host "`n[1/4] Verificando dependencias de runtime..." -ForegroundColor Yellow
& $pythonCmd -c "import requests, keyboard, PIL, pystray, ttkbootstrap, pyperclip" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando dependencias desde requirements.txt..." -ForegroundColor Yellow
    & $pythonCmd -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "No se pudieron instalar las dependencias."
        exit $LASTEXITCODE
    }
}

# 3. Validar PyInstaller
Write-Host "`n[2/4] Verificando PyInstaller..." -ForegroundColor Yellow
& $pythonCmd -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando PyInstaller..." -ForegroundColor Yellow
    & $pythonCmd -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Error "No se pudo instalar PyInstaller."
        exit $LASTEXITCODE
    }
}

# 4. Compilar con PyInstaller
Write-Host "`n[3/4] Compilando con PyInstaller..." -ForegroundColor Yellow
& $pythonCmd -m PyInstaller Escriba.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Error "La compilacion con PyInstaller fallo con codigo $LASTEXITCODE."
    exit $LASTEXITCODE
}

# 5. Iniciar nuevo EXE
Write-Host "`n[4/4] Resultado:" -ForegroundColor Green
$exePath = Join-Path $PSScriptRoot "dist\Escriba.exe"
if (Test-Path $exePath) {
    $fileInfo = Get-Item $exePath
    $sizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
    Write-Host " Escriba.exe generado exitosamente ($sizeMB MB)." -ForegroundColor Green
    Write-Host " Ubicacion: $exePath" -ForegroundColor DarkCyan

    if (-not $NoStart) {
        Write-Host "`n Iniciando nuevo Escriba.exe..." -ForegroundColor Yellow
        Start-Process $exePath
    }
} else {
    Write-Error "No se encontro el archivo compilado en $exePath."
    exit 1
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host " Build completado exitosamente." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
