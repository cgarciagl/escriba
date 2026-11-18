# Escriba — Agent Instructions

## Después de cada modificación a `escriba.py` o `Escriba.spec`

Cada vez que modifiques cualquier archivo del proyecto, ejecuta los siguientes pasos **en orden**:

### 1. Cerrar el EXE si está corriendo

```powershell
$proc = Get-Process -Name "Escriba" -ErrorAction SilentlyContinue
if ($proc) {
    Stop-Process -Name "Escriba" -Force
    Start-Sleep -Milliseconds 1500
    Write-Host "Escriba.exe cerrado."
} else {
    Write-Host "Escriba.exe no estaba corriendo."
}
```

### 2. Compilar

```powershell
Set-Location C:\Sistemas\Repos\escriba
pyinstaller Escriba.spec --clean --noconfirm
```

Verifica que el comando terminó con exit code 0 antes de continuar.
Si falla, reporta el error al usuario y **no ejecutes el paso 3**.

### 3. Ejecutar el nuevo EXE

```powershell
Start-Process "C:\Sistemas\Repos\escriba\dist\Escriba.exe"
```

---

## Reglas generales del proyecto

- El punto de entrada principal es `escriba.py` (orquestando los módulos existentes en el repositorio). No crear archivos Python adicionales salvo que el usuario lo pida.
- La compilación siempre usa `Escriba.spec` (no `pyinstaller escriba.py` directo).
- El EXE compilado queda en `dist\Escriba.exe`.
- No modificar `config.json` — es generado en tiempo de ejecución.
- Verificar antes de cerrar con `ruff check .` y `python -m pytest -q`.
- Stack: `ttkbootstrap`, `pystray`, `Pillow`, `pyperclip`, `ctypes`, `requests`. No agregar dependencias sin confirmar con el usuario.
