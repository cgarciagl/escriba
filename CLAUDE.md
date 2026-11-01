# Escriba — Claude Instructions

## Visión general

**Escriba** es una aplicación de escritorio para Windows que actúa como asistente de texto con IA. El usuario selecciona texto en cualquier aplicación, pulsa **Win+Alt+E**, y aparece un menú flotante con acciones de IA (reescribir, traducir, resumir, formatear SQL, etc.). El resultado puede sustituir directamente el texto seleccionado.

- **Versión:** 1.0.0
- **Plataforma:** Windows (usa `ctypes.windll`, `winreg`, `RegisterHotKey`)
- **Hotkey global:** `Win+Alt+E` (registrada via Windows API `RegisterHotKey`, no la librería `keyboard`)

---

## Después de cada modificación a cualquier archivo del proyecto

Ejecuta los siguientes pasos **en orden**:

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

## Arquitectura del proyecto

| Archivo | Responsabilidad |
|---|---|
| `escriba.py` | Punto de entrada. Clase `EscribaApp` que orquesta hotkey, tray y ventanas. |
| `constants.py` | Constantes globales (`APP_NAME`, rutas, API URLs, `AI_ACTIONS`). |
| `config.py` | `ConfigManager` — lectura/escritura de `%APPDATA%\\Escriba\\config.json` con cache en memoria; API Key cifrada con DPAPI (`get_api_key`/`set_api_key`). |
| `ai_clients.py` | `GeminiClient` (API oficial de Google Gemini, reintentos con backoff exponencial) y `generate_text()`, punto de entrada único para la UI. |
| `hotkey.py` | `HotkeyManager` — registra `Win+Alt+E` via `RegisterHotKey`. Helpers `send_ctrl_c`, `send_ctrl_v`. |
| `ui_windows.py` | Toda la UI: `FloatingMenu`, `ResultWindow`, `ConfigWindow`, `ThinkingWindow`, `SplashBanner`, `TooltipNotification`, `CustomPromptWindow`. |
| `tray.py` | `TrayIconManager` — ícono en la bandeja del sistema via `pystray`. |
| `startup.py` | `StartupManager` — registro/desregistro en `HKCU\...\Run` para auto-inicio con Windows. |
| `Escriba.spec` | Configuración PyInstaller. Genera `dist\Escriba.exe` como ejecutable single-file sin consola. |

### Flujo principal

1. `EscribaApp.__init__` crea el root `ttkbootstrap.Window` (tema "vapor") y todas las ventanas.
2. `run()` carga config, inicia el tray icon, muestra `SplashBanner`, y arranca el hotkey manager.
3. Al pulsar Win+Alt+E → `_on_hotkey` → `_capture_selected_text` (simula Ctrl+C, lee portapapeles, restaura el original) → muestra `FloatingMenu`.
4. El usuario elige una acción → `ThinkingWindow` (indicador de progreso) → `generate_text` en hilo secundario → `ResultWindow` con el resultado.
5. Desde `ResultWindow` el usuario puede copiar, editar, regenerar, o **sustituir** el texto en la aplicación original (simula Ctrl+V).

### Cliente de IA

- **Proveedor único:** Google Gemini (`generativelanguage.googleapis.com/v1beta`), API Key en la configuración (cifrada).
- `GeminiClient.generate()` reintenta errores transitorios (429/5xx, red, "modelo ocupado") con retroceso exponencial y jitter.
- `generate_text()` es el punto de entrada de la UI; si se agregan proveedores, el fallback va ahí.

---

## Reglas generales del proyecto

- El archivo principal es `escriba.py`. No crear archivos Python adicionales salvo que el usuario lo pida.
- La compilación siempre usa `Escriba.spec` (no `pyinstaller escriba.py` directo).
- El EXE compilado queda en `dist\Escriba.exe`.
- No modificar `config.json` — es generado en tiempo de ejecución (en `%APPDATA%\\Escriba`).
- Los tests deben poder correr fuera de Windows (`tests/conftest.py` simula `winreg`, `ctypes.windll`, etc.): `python -m pytest -q`.
- Stack: `ttkbootstrap`, `pystray`, `Pillow`, `pyperclip`, `ctypes`, `requests`, `keyboard`. No agregar dependencias sin confirmar con el usuario.
- La UI usa `ttkbootstrap` con tema "vapor" y colores custom definidos en `ui_windows.py` (paleta `_FM_*`).
- Los hilos secundarios usan `app.schedule()` para actualizar la UI en el hilo principal de Tk.
- El idioma del proyecto es español (nombres de variables, comentarios, prompts de IA, UI).
