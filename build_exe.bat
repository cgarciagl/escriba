@echo off
setlocal

cd /d "%~dp0"

echo ============================================
echo  Escriba - Build EXE
echo ============================================
echo.

:: Detectar si se debe omitir 'pause' (en PowerShell, CI o con flags)
set "NO_PAUSE="
for %%A in (%*) do (
    if /i "%%A"=="-nopause" set "NO_PAUSE=1"
    if /i "%%A"=="--no-pause" set "NO_PAUSE=1"
    if /i "%%A"=="-q" set "NO_PAUSE=1"
    if /i "%%A"=="-quiet" set "NO_PAUSE=1"
)
if defined POWERSHELL_DISTRIBUTION_CHANNEL set "NO_PAUSE=1"
if defined __PSLockDownPolicy set "NO_PAUSE=1"
if defined CI set "NO_PAUSE=1"

:: Verificar que Python está disponible (detecta 'py' o 'python')
set "PYTHON_CMD="
where py >nul 2>&1 && set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
    where python >nul 2>&1 && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo [ERROR] Ni 'py' ni 'python' fueron encontrados en el PATH. Instala Python para continuar.
    if not defined NO_PAUSE pause
    exit /b 1
)

:: Cerrar Escriba.exe si está corriendo para evitar que dist\Escriba.exe esté bloqueado
echo [0/4] Cerrando Escriba.exe si esta corriendo...
taskkill /f /im Escriba.exe >nul 2>&1
timeout /t 1 /nobreak >nul 2>&1

:: Verificar dependencias de runtime
echo.
echo [1/4] Verificando dependencias de runtime...
%PYTHON_CMD% -c "import requests, keyboard, PIL, pystray, ttkbootstrap, pyperclip" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Faltan dependencias del proyecto. Instalando requirements.txt...
    %PYTHON_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar las dependencias del proyecto.
        if not defined NO_PAUSE pause
        exit /b 1
    )
)

:: Verificar PyInstaller
echo.
echo [2/4] Verificando PyInstaller...
%PYTHON_CMD% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller no esta instalado. Instalando...
    %PYTHON_CMD% -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar PyInstaller.
        if not defined NO_PAUSE pause
        exit /b 1
    )
)

:: Limpiar builds anteriores
if exist "dist\Escriba.exe" del /f /q "dist\Escriba.exe" >nul 2>&1
if exist "build\Escriba" rmdir /s /q "build\Escriba" >nul 2>&1

:: Compilar
echo.
echo [3/4] Compilando con PyInstaller...
%PYTHON_CMD% -m PyInstaller Escriba.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] La compilacion fallo. Revisa los mensajes anteriores.
    if not defined NO_PAUSE pause
    exit /b 1
)

:: Resultado
echo.
echo [4/4] Resultado:
if exist "dist\Escriba.exe" (
    for %%F in ("dist\Escriba.exe") do echo  Escriba.exe generado: %%~zF bytes ^(%%~zF / 1048576 MB aprox^)
    echo.
    echo  Ubicacion: %~dp0dist\Escriba.exe
    echo.
    echo  Iniciando nuevo Escriba.exe...
    start "" "%~dp0dist\Escriba.exe"
) else (
    echo [ERROR] No se encontro el ejecutable generado.
    if not defined NO_PAUSE pause
    exit /b 1
)

echo.
echo ============================================
echo  Build completado exitosamente.
echo ============================================

if not defined NO_PAUSE pause
endlocal
exit /b 0
