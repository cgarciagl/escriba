# Escriba — Claude Instructions

## Visión general

**Escriba** es una aplicación de escritorio para Windows (y, de forma experimental, macOS) que actúa como asistente de texto con IA. El usuario selecciona texto en cualquier aplicación, pulsa **Win+Alt+E**, y aparece un menú flotante con acciones de IA (reescribir, traducir, resumir, formatear SQL, etc.). El resultado puede sustituir directamente el texto seleccionado.

- **Versión:** 1.2.0
- **Plataformas:** Windows (`ctypes.windll`, `winreg`, `RegisterHotKey`) y macOS experimental (`pynput`, PyObjC). Todo lo dependiente del sistema pasa por `plataforma.py`.
- **Hotkey global:** `Win+Alt+E` en Windows (`RegisterHotKey`); `Ctrl+Cmd+E` en macOS (`pynput`).

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

### En macOS (si se trabaja desde un Mac)

```bash
pkill -x Escriba; sleep 1
pyinstaller Escriba.spec --clean --noconfirm && open dist/Escriba.app
```

---

## Arquitectura del proyecto

| Archivo | Responsabilidad |
|---|---|
| `escriba.py` | Punto de entrada. Clase `EscribaApp` que orquesta hotkey, tray y ventanas. |
| `constants.py` | Constantes globales (`APP_NAME`, rutas, API URLs, `AI_ACTIONS` predeterminadas). |
| `actions.py` | Carga y valida `%APPDATA%\\Escriba\\actions.json` (acciones personalizadas); `shortcut_to_tk`. |
| `history.py` | `History` — últimas respuestas en memoria (submenú de la bandeja). |
| `config.py` | `ConfigManager` — lectura/escritura de `%APPDATA%\\Escriba\\config.json` con cache en memoria; secretos cifrados con DPAPI (`get_secret`/`set_secret`, `get_api_key`, `get_openai_api_key`). |
| `ai_clients.py` | `GeminiClient`, `OpenAICompatibleClient` (streaming, system instruction, reintentos) y `generate_text()`, punto de entrada único para la UI (aplica el fallback). |
| `plataforma.py` | Capa de plataforma: `HotkeyManager`, `send_copy`/`send_paste`, `get_foreground_window`/`activate_window`, `StartupManager`, `HOTKEY_LABEL`, `tk_shortcut`. Elige Windows o macOS. |
| `hotkey.py` | (Windows) `HotkeyManager` — registra `Win+Alt+E` via `RegisterHotKey`. Helpers `send_ctrl_c`, `send_ctrl_v`. |
| `macos.py` | (macOS) atajo con `pynput`, `⌘C/⌘V` con Quartz, app activa con `NSWorkspace`, `StartupManager` (LaunchAgent) y Llavero (`security`). |
| `ui_windows.py` | Fachada que reexporta la UI. |
| `ui_common.py` | Paleta `_FM_*`, helpers (`apply_dark_style`, `center_window`, `fade_window`), `TooltipNotification`, `ThinkingWindow`, `SplashBanner`. |
| `ui_menu.py` | `FloatingMenu` (acciones de `actions.json` + atajos) y `CustomPromptWindow`. |
| `ui_result.py` | `run_ai_action`/`start_ai_action` (streaming, historial) y `ResultWindow`. |
| `ui_config.py` | `ConfigWindow` con pestañas Gemini / Proveedor alternativo / General. |
| `tray.py` | `TrayIconManager` — ícono en la bandeja del sistema via `pystray`. |
| `startup.py` | (Windows) `StartupManager` — registro/desregistro en `HKCU\...\Run` para auto-inicio. |
| `Escriba.spec` | Configuración PyInstaller. Windows: `dist\Escriba.exe` (single-file, sin consola). macOS: `dist/Escriba.app` (onedir + BUNDLE, `LSUIElement`). |

### Flujo principal

1. `EscribaApp.__init__` crea el root `ttkbootstrap.Window` (tema "vapor") y todas las ventanas.
2. `run()` carga config, inicia el tray icon, muestra `SplashBanner`, y arranca el hotkey manager.
3. Al pulsar Win+Alt+E → `_on_hotkey` → `_capture_selected_text` (simula Ctrl+C, lee portapapeles, restaura el original) → muestra `FloatingMenu`.
4. El usuario elige una acción → `ThinkingWindow` → `generate_text` en hilo secundario → con el primer fragmento se abre `ResultWindow` en modo streaming → `finish()` habilita los botones y la respuesta pasa al historial.
5. Desde `ResultWindow` el usuario puede copiar, editar, regenerar, o **sustituir** el texto en la aplicación original (simula Ctrl+V).

### Clientes de IA

- **Gemini** (`generativelanguage.googleapis.com/v1beta`) y **OpenAI-compatible** (Ollama, OpenAI, OpenRouter…), seleccionables con `provider` en la configuración.
- El prompt de la acción va como *system instruction*; el texto seleccionado, como mensaje del usuario.
- `run_with_retries()` reintenta errores transitorios (429/5xx, red, "modelo ocupado") con backoff exponencial y jitter; con streaming no reintenta tras emitir texto.
- `generate_text()` aplica el fallback al otro proveedor (`fallback_enabled`) solo si el primero no emitió texto.

---

## Reglas generales del proyecto

- El archivo principal es `escriba.py`. No crear archivos Python adicionales salvo que el usuario lo pida. Si se agrega uno, incluirlo en `hiddenimports` de `Escriba.spec`.
- La compilación siempre usa `Escriba.spec` (no `pyinstaller escriba.py` directo).
- El EXE compilado queda en `dist\Escriba.exe`.
- No modificar `config.json` — es generado en tiempo de ejecución (en `%APPDATA%\\Escriba`).
- Los tests de UI (`tests/test_ui.py`) necesitan Tk real: se omiten sin Tk y corren en la CI de Windows y macOS (en un proceso aparte).
- La CI (`.github/workflows/tests.yml`) además compila `Escriba.exe` y `Escriba.app`, comprueba que arrancan y los publica como artefactos.
- Los tests deben poder correr fuera de Windows (`tests/conftest.py` simula `winreg`, `ctypes.windll`, etc.): `python -m pytest -q`.
- Stack: `ttkbootstrap`, `pystray`, `Pillow`, `pyperclip`, `ctypes`, `requests`, `keyboard` (solo Windows), `pynput` y `pyobjc-framework-Cocoa/Quartz` (solo macOS, con marcadores en `requirements.txt`). No agregar dependencias sin confirmar con el usuario.
- No usar `ctypes.windll`, `winreg` ni APIs de PyObjC fuera de `hotkey.py`, `startup.py`, `config.py` (DPAPI), `plataforma.py` y `macos.py`: el resto del código debe pasar por `plataforma.py`.
- En macOS, `NSApplication` debe crearse **después** del root de Tk (`init_app()` va tras `tb.Window`) y `pystray` usa `run_detached()` en el hilo principal.
- Fuentes: usar `UI_FONT`, `MONO_FONT`, `EMOJI_FONT` de `ui_common.py` (Segoe UI no existe en macOS).
- La UI usa `ttkbootstrap` con tema "vapor" y colores custom definidos en `ui_windows.py` (paleta `_FM_*`).
- Los hilos secundarios usan `app.schedule()` para actualizar la UI en el hilo principal de Tk.
- El idioma del proyecto es español (nombres de variables, comentarios, prompts de IA, UI).
