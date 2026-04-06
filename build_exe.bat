@echo off
setlocal

echo ============================================
echo  Escriba - Build EXE
echo ============================================
echo.

:: Verificar que pyinstaller está disponible
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller no encontrado. Instala con: pip install pyinstaller
    pause
    exit /b 1
)

:: Limpiar builds anteriores
echo [1/3] Limpiando builds anteriores...
if exist "dist\Escriba.exe" del /f /q "dist\Escriba.exe"
if exist "build\Escriba" rmdir /s /q "build\Escriba"

:: Compilar
echo [2/3] Compilando con PyInstaller...
pyinstaller Escriba.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] La compilacion fallo. Revisa los mensajes anteriores.
    pause
    exit /b 1
)

:: Resultado
echo.
echo [3/3] Resultado:
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
echo ============================================
echo  Build completado exitosamente.
echo ============================================
pause
endlocal
