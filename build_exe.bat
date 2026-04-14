@echo off
setlocal

echo ============================================
echo  Escriba - Build EXE
echo ============================================
echo.

:: Verificar que Python está disponible
where py >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python Launcher no encontrado. Instala Python para continuar.
    pause
    exit /b 1
)

:: Verificar dependencias de runtime
echo [0/4] Verificando dependencias de runtime...
py -c "import requests, keyboard, PIL, pystray, ttkbootstrap, pyperclip" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Faltan dependencias del proyecto. Instalando requirements.txt...
    py -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar las dependencias del proyecto.
        pause
        exit /b 1
    )
)

:: Verificar PyInstaller
py -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller no esta instalado. Instalando...
    py -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] No se pudo instalar PyInstaller.
        pause
        exit /b 1
    )
)

:: Limpiar builds anteriores
echo [1/4] Limpiando builds anteriores...
if exist "dist\Escriba.exe" del /f /q "dist\Escriba.exe"
if exist "build\Escriba" rmdir /s /q "build\Escriba"

:: Compilar
echo [2/4] Compilando con PyInstaller...
py -m PyInstaller Escriba.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] La compilacion fallo. Revisa los mensajes anteriores.
    pause
    exit /b 1
)

:: Resultado
echo.
echo [3/4] Resultado:
if exist "dist\Escriba.exe" (
    for %%F in ("dist\Escriba.exe") do echo  Escriba.exe generado: %%~zF bytes ^(%%~zF / 1048576 MB aprox^)
    echo.
    echo  Ubicacion: %~dp0dist\Escriba.exe
) else (
    echo [ERROR] No se encontro el ejecutable generado.
    pause
    exit /b 1
)

echo.
echo [4/4] Dependencias validadas y build completado.
echo.
echo ============================================
echo  Build completado exitosamente.
echo ============================================
pause
endlocal
