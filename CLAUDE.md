# Escriba — Claude Instructions

## Visión general

**Escriba** es una aplicación de escritorio multiplataforma (Windows, macOS y Linux X11) que actúa como asistente de texto con IA. El usuario selecciona texto en cualquier aplicación (o sitúa el cursor para redactar desde cero), pulsa **Win+Alt+E**, y aparece un menú flotante con acciones de IA (reescribir, traducir, resumir, formatear SQL, etc.). El resultado puede sustituir directamente el texto seleccionado.

- **Versión:** `APP_VERSION` en `constants.py` (actualmente `1.0.3`)
- **Plataformas:** Windows (`ctypes.windll`, `winreg`, `RegisterHotKey`), macOS (`pynput`, PyObjC) y Linux X11 (`pynput`, `xdotool`, `xclip`). Todo lo dependiente del sistema pasa por `plataforma.py`.
- **Hotkey global:** Configurable desde Configuración (`Win+Alt+E` en Windows, `Ctrl+Cmd+E` en macOS, `Ctrl+Alt+E` en Linux).

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
| `escriba.py` | Punto de entrada (`main()` con guardia de instancia única). Clase `EscribaApp` que orquesta hotkey, tray y ventanas. |
| `constants.py` | Constantes globales (`APP_NAME`, `APP_VERSION`, rutas, API URLs, `AI_ACTIONS` predeterminadas). |
| `actions.py` | Carga/valida `actions.json` (soporta `mode`, `temperature`, `model`, `strip_markdown`, `auto_replace`), variables `{clipboard}`/`{lang}`/`{date}`/`{time}`/`{datetime}`/`{input:...}`, `strip_code_fences`, `export_actions`/`import_actions`. |
| `history.py` | `History` — últimas respuestas en memoria (submenú de la bandeja). |
| `config.py` | `ConfigManager` — lectura/escritura atómica de `config.json` con cache en memoria; secretos cifrados con DPAPI (Windows) o Llavero (macOS). |
| `ai_clients.py` | `GeminiClient`, `OpenAICompatibleClient` (streaming, system instruction, temperatura, modelo por acción, historial multi-turno, reintentos) y `generate_text()`. |
| `plataforma.py` | Capa de plataforma: `HotkeyManager`, `send_copy`/`send_paste`, `get_foreground_window`/`activate_window`, `StartupManager`, `clipboard_has_non_text`, `acquire_single_instance`/`release_single_instance`, `active_hotkey_label`, `tk_shortcut`. |
| `hotkey.py` | (Windows) `HotkeyManager` configurable via `RegisterHotKey`. Helpers `send_ctrl_c`, `send_ctrl_v`. |
| `macos.py` | (macOS) atajo con `pynput`, `⌘C/⌘V` con Quartz, app activa con `NSWorkspace`, `StartupManager` (LaunchAgent) y Llavero (`security -i`). |
| `linux_platform.py` | (Linux X11) atajo con `pynput`, `xdotool`, `xclip`, portapapeles y arranque `.desktop`. |
| `updater.py` | Auto-actualización contra GitHub Releases (`ReleaseInfo` con `release_notes`, descarga segura y extracción verificada). |
| `ui_windows.py` | Fachada que reexporta la UI. |
| `ui_common.py` | Paleta `_FM_*`, estilos ttk `Escriba.*`, DPI awareness, `TooltipNotification`, `ThinkingWindow`, `SplashBanner`, `AboutWindow`, `UpdateDialog`. |
| `ui_menu.py` | `FloatingMenu`: paleta de comandos con scroll, modos `selection`/`compose`/`both`, diálogo de variables `{input:...}` e instrucción libre. |
| `ui_result.py` | `run_ai_action`/`start_ai_action` y `ResultWindow` (streaming, diff, Markdown, historial de sesión `◀`/`▶`, contador de palabras, ajuste multi-turno). |
| `ui_config.py` | `ConfigWindow` con pestañas Gemini / Proveedor alternativo / Acciones (editor visual + importar/exportar) / General. |
| `tray.py` | `TrayIconManager` — ícono y tooltip dinámico en la bandeja del sistema via `pystray`. |
| `startup.py` | (Windows) `StartupManager` — registro/desregistro en `HKCU\...\Run` para auto-inicio. |
| `Escriba.spec` | Configuración PyInstaller. Windows: `dist\Escriba.exe`, macOS: `dist/Escriba.app`, Linux: `dist/Escriba`. |

### Flujo principal

1. `main()` adquiere el bloqueo de instancia única (`acquire_single_instance()`) y lanza `EscribaApp`.
2. `run()` carga config, inicia el tray icon, muestra `SplashBanner`, arranca el hotkey manager y programa la comprobación de actualizaciones.
3. Al pulsar el atajo global → `_on_hotkey` → `_capture_selected_text` (preserva datos no textuales del portapapeles si no hay texto) → muestra `FloatingMenu`.
4. El usuario filtra/elige una acción o escribe una instrucción → si la acción tiene `{input:...}`, solicita los valores → `start_ai_action` crea un `_ResultSession` → `ThinkingWindow` → `generate_text` en hilo secundario → `ResultWindow` en modo streaming → `finish()` habilita los botones y guarda en historial.
5. Desde `ResultWindow` el usuario puede copiar, editar, regenerar, navegar entre refinamientos (`◀`/`▶`), ver diff o **sustituir/insertar** el texto en la aplicación original.

### Clientes de IA

- **Gemini** (`generativelanguage.googleapis.com/v1beta`) y **OpenAI-compatible** (Ollama, OpenAI, OpenRouter…), seleccionables con `provider` en la configuración.
- El prompt de la acción va como *system instruction*; el texto seleccionado (y el historial multi-turno al ajustar), como mensajes de conversación.
- `run_with_retries()` reintenta errores transitorios (429/5xx, red, "modelo ocupado") con backoff exponencial y jitter; con streaming no reintenta tras emitir texto.
- `generate_text()` aplica el fallback al otro proveedor (`fallback_enabled`) solo si el primero no emitió texto (sin propagar el `model` específico del primer proveedor).

---

## Reglas generales del proyecto

- El archivo principal es `escriba.py`. No crear archivos Python adicionales salvo que el usuario lo pida. Si se agrega uno, incluirlo en `hiddenimports` de `Escriba.spec`.
- La compilación siempre usa `Escriba.spec` (no `pyinstaller escriba.py` directo).
- El EXE compilado queda en `dist\Escriba.exe`.
- No modificar `config.json` — es generado en tiempo de ejecución (en `%APPDATA%\\Escriba`).
- Los tests de UI (`tests/test_ui.py`) necesitan Tk real: se omiten sin Tk y corren en la CI de Windows, macOS y Linux (`xvfb-run`).
- La CI (`.github/workflows/tests.yml`) ejecuta `ruff check .`, `pytest`, compila `Escriba.exe`, `Escriba.app` y el binario Linux, comprueba que arrancan y los publica como artefactos.
- Los tests deben poder correr fuera de Windows (`tests/conftest.py` simula `winreg`, `ctypes.windll`, etc.): `python -m pytest -q` y `ruff check .`.
- Stack: `ttkbootstrap`, `pystray`, `Pillow`, `pyperclip`, `ctypes`, `requests`, `keyboard` (solo Windows), `pynput` y `pyobjc-framework-Cocoa/Quartz` (solo macOS, con marcadores en `requirements.txt`). No agregar dependencias sin confirmar con el usuario.
- No usar `ctypes.windll`, `winreg` ni APIs de PyObjC fuera de `hotkey.py`, `startup.py`, `config.py` (DPAPI), `plataforma.py` y `macos.py`: el resto del código debe pasar por `plataforma.py`.
- En macOS, `NSApplication` debe crearse **después** del root de Tk (`init_app()` va tras `tb.Window`) y `pystray` usa `run_detached()` en el hilo principal.
- Fuentes: usar `UI_FONT`, `MONO_FONT`, `EMOJI_FONT` de `ui_common.py` (Segoe UI no existe en macOS).
- La UI usa `ttkbootstrap` con tema "vapor" como base, pero los colores salen de la paleta `_FM_*` de `ui_common.py`. Para botones secundarios, campos, combos, pestañas y scrollbars usar los estilos `Escriba.*` (no `bootstyle="secondary"`/`info`/`danger`, que el tema pinta de rosa/morado/cian). El único `bootstyle` permitido es `warning` (ámbar) para la acción principal y los indicadores de casillas.
- Tamaños en píxeles: pasar por `scaled()`/`center_window()` para respetar el escalado de pantalla.
- Cambios visuales: revisar las capturas de `tools/capturas.py` (artefacto "capturas" de la CI) antes de dar el trabajo por terminado, y actualizar las del README en `docs/capturas/` si cambió lo que muestran.
- Los hilos secundarios usan `app.schedule()` para actualizar la UI en el hilo principal de Tk.
- El idioma del proyecto es español (nombres de variables, comentarios, prompts de IA, UI).
