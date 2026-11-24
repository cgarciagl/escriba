# Escriba — Agent Instructions

## Visión general

**Escriba** es una aplicación de escritorio multiplataforma (Windows, macOS y Linux X11) que actúa como asistente de texto con IA. El usuario selecciona texto en cualquier aplicación (o sitúa el cursor para redactar desde cero), pulsa **Win+Alt+E**, y aparece un menú flotante con acciones de IA (reescribir, traducir, resumir, formatear SQL, etc.). El resultado puede sustituir directamente el texto seleccionado.

- **Versión:** `APP_VERSION` en `constants.py` (actualmente `1.0.6`)
- **Plataformas:** Windows (`ctypes.windll`, `winreg`, `RegisterHotKey`), macOS (`pynput`, PyObjC) y Linux X11/Wayland (`pynput`, `xdotool`, `xclip`, respaldo `wtype`). Todo lo dependiente del sistema pasa por `plataforma.py`.
- **Hotkey global:** Configurable desde Configuración (`Win+Alt+E` en Windows, `Ctrl+Cmd+E` en macOS, `Ctrl+Alt+E` en Linux) más atajo opcional de repetición (`repeat_hotkey`).

---

## Después de cada modificación a cualquier archivo del proyecto

Cada vez que modifiques cualquier archivo del proyecto (`escriba.py`, `Escriba.spec`, módulos, etc.), ejecuta los siguientes pasos **en orden**:

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
| `escriba.py` | Punto de entrada (`main()` con guardia de instancia única). Clase `EscribaApp` que orquesta hotkey principal, hotkey de repetición (`repeat_hotkey`), aviso Wayland, tray y ventanas. |
| `constants.py` | Constantes globales (`APP_NAME`, `APP_VERSION`, `DEFAULT_REPEAT_HOTKEY`, rutas, API URLs, `AI_ACTIONS` predeterminadas incluyendo `Redacción`). |
| `actions.py` | Carga/valida `actions.json` (soporta `mode`, `apps`, `temperature`, `model`, `strip_markdown`, `auto_replace`), variables `{app}`/`{clipboard}`/`{lang}`/`{date}`/`{time}`/`{datetime}`/`{input:...}`, `add_custom_action`, `action_matches_app`, `strip_code_fences`, `export_actions`/`import_actions`. |
| `history.py` | `History` — últimas respuestas en memoria con persistencia opcional en `history.json` (`0600`, submenú de la bandeja). |
| `config.py` | `ConfigManager` — lectura/escritura atómica de `config.json` con cache en memoria; secretos cifrados con DPAPI (Windows) o Llavero (macOS). |
| `ai_clients.py` | `GeminiClient`, `OpenAICompatibleClient` (streaming, system instruction, temperatura, modelo por acción, historial multi-turno, reintentos) y `generate_text()`. |
| `plataforma.py` | Capa de plataforma: `HotkeyManager` (con `hotkey_id`), `send_copy`/`send_paste`, `clipboard_copy`/`clipboard_paste`, `get_foreground_window`/`get_foreground_app_name`/`activate_window`, `StartupManager`, `clipboard_has_non_text`, `markdown_to_html`/`copy_rich_text`, `is_wayland`, `acquire_single_instance`/`release_single_instance`, `active_hotkey_label`, `tk_shortcut`. |
| `hotkey.py` | (Windows) `HotkeyManager` configurable via `RegisterHotKey` con `hotkey_id`. Helpers `send_ctrl_c`, `send_ctrl_v`. |
| `macos.py` | (macOS) atajo con `pynput`, `⌘C/⌘V` con Quartz, app activa y `get_foreground_app_name` con `NSWorkspace`, `StartupManager` (LaunchAgent) y Llavero (`security -i`). |
| `linux_platform.py` | (Linux X11/Wayland) atajo con `pynput`, `xdotool`, `xclip`, detección Wayland (`is_wayland`/`has_wayland_tools`), portapapeles `wl-copy`/`wl-paste`, foco/app en Hyprland/Sway y respaldo `wtype`, más arranque `.desktop`. |
| `updater.py` | Auto-actualización contra GitHub Releases (`ReleaseInfo` con `release_notes`, descarga segura y extracción verificada). |
| `ui_windows.py` | Fachada que reexporta la UI. |
| `ui_common.py` | Paleta `_FM_*`, estilos ttk `Escriba.*`, DPI awareness, `TooltipNotification`, `ThinkingWindow`, `SplashBanner`, `AboutWindow`, `UpdateDialog`. |
| `ui_menu.py` | `FloatingMenu`: paleta de comandos con scroll, filtrado por `mode` y `apps`, prompts recientes (`recent_prompts`), guardado rápido (`★ Guardar`/`Ctrl+S`), diálogo de variables `{input:...}` e instrucción libre. |
| `ui_result.py` | `run_ai_action`/`start_ai_action` y `ResultWindow` (streaming, diff, Markdown, historial de sesión `◀`/`▶`, contador de palabras y latencia, ajuste multi-turno, encadenamiento `🔗 Encadenar`, pegado HTML con `rich_paste`). |
| `ui_config.py` | `ConfigWindow` con pestañas Gemini / Proveedor alternativo / Acciones (editor visual con `apps` + importar/exportar) / General (`repeat_hotkey`, `rich_paste`, `persist_history`). |
| `tray.py` | `TrayIconManager` — ícono y tooltip dinámico en la bandeja del sistema via `pystray`. |
| `startup.py` | (Windows) `StartupManager` — registro/desregistro en `HKCU\...\Run` para auto-inicio. |
| `Escriba.spec` | Configuración PyInstaller. Windows: `dist\Escriba.exe`, macOS: `dist/Escriba.app`, Linux: `dist/Escriba`. |

### Flujo principal

1. `main()` adquiere el bloqueo de instancia única (`acquire_single_instance()`) y lanza `EscribaApp`.
2. `run()` carga config, inicia el tray icon, muestra `SplashBanner`, arranca `hotkey` y (si está configurado) `repeat_hotkey`, avisa si detecta Wayland y programa la comprobación de actualizaciones.
3. Al pulsar el atajo global → `_on_hotkey` → `_capture_selected_text` (preserva datos no textuales del portapapeles si no hay texto) → muestra `FloatingMenu` (con detección de la app activa y prompts recientes).
4. El usuario filtra/elige una acción o escribe una instrucción (o pulsa `repeat_hotkey` para repetir la última acción directo) → si la acción tiene `{input:...}`, solicita los valores → `start_ai_action` crea un `_ResultSession` → `ThinkingWindow` → `generate_text` en hilo secundario → `ResultWindow` en modo streaming → `finish()` habilita los botones, muestra la latencia y guarda en historial.
5. Desde `ResultWindow` el usuario puede copiar, editar, regenerar, **encadenar** otra acción sobre el resultado, navegar entre refinamientos (`◀`/`▶`), ver diff o **sustituir/insertar** el texto (en texto plano o formato enriquecido HTML) en la aplicación original.

### Clientes de IA

- **Gemini** (`generativelanguage.googleapis.com/v1beta`) y **OpenAI-compatible** (Ollama, OpenAI, OpenRouter…), seleccionables con `provider` en la configuración.
- El prompt de la acción va como *system instruction*; el texto seleccionado (y el historial multi-turno al ajustar), como mensajes de conversación.
- `run_with_retries()` reintenta errores transitorios (429/5xx, red, "modelo ocupado") con backoff exponencial y jitter; con streaming no reintenta tras emitir texto.
- `generate_text()` aplica el fallback al otro proveedor (`fallback_enabled`) solo si el primero no emitió texto (sin propagar el `model` específico del primer proveedor).

---

## Reglas generales del proyecto

- El punto de entrada principal es `escriba.py` (orquestando los módulos existentes en el repositorio). No crear archivos Python adicionales salvo que el usuario lo pida. Si se agrega uno, incluirlo en `hiddenimports` de `Escriba.spec`.
- La compilación siempre usa `Escriba.spec` (no `pyinstaller escriba.py` directo).
- El EXE compilado queda en `dist\Escriba.exe`.
- No modificar `config.json` — es generado en tiempo de ejecución (en `%APPDATA%\\Escriba`).
- Verificar antes de cerrar con `ruff check .` y `python -m pytest -q`.
- Los tests de UI (`tests/test_ui.py`) necesitan Tk real: se omiten sin Tk y corren en la CI de Windows, macOS y Linux (`xvfb-run`).
- La CI (`.github/workflows/tests.yml`) ejecuta `ruff check .`, `pytest`, compila `Escriba.exe`, `Escriba.app` y el binario Linux, comprueba que arrancan y los publica como artefactos.
- Los tests deben poder correr fuera de Windows (`tests/conftest.py` simula `winreg`, `ctypes.windll`, etc.): `python -m pytest -q` y `ruff check .`.
- Stack: `ttkbootstrap`, `pystray`, `Pillow`, `pyperclip`, `ctypes`, `requests`, `keyboard` (solo Windows), `pynput` y `pyobjc-framework-Cocoa/Quartz` (solo macOS, con marcadores en `requirements.txt`). No agregar dependencias sin confirmar con el usuario.
- No usar `ctypes.windll`, `winreg` ni APIs de PyObjC fuera de `hotkey.py`, `startup.py`, `config.py` (DPAPI), `plataforma.py` y `macos.py`: el resto del código debe pasar por `plataforma.py`.
- En macOS, `NSApplication` debe crearse **después** del root de Tk (`init_app()` va tras `tb.Window`) y `pystray` usa `run_detached()` en el hilo principal.
- Fuentes: usar `UI_FONT`, `MONO_FONT`, `EMOJI_FONT` de `ui_common.py` (Segoe UI no existe en macOS).
- La UI usa `ttkbootstrap` con tema "vapor" como base, pero los colores salen de la paleta `_FM_*` de `ui_common.py`. Para botones secundarios, campos, combos, pestañas y scrollbars usar los estilos `Escriba.*` (no `bootstyle="secondary"`/`info`/`danger`, que el tema pinta de rosa/morado/cian). El único `bootstyle` permitido es `warning` (ámbar) para la acción principal y los indicadores de casillas.
- Tamaños en píxeles: pasar por `scaled()`/`center_window()` para respetar el escalado de pantalla.
- Cambios visuales: revisar las capturas de `tools/capturas.py` en ambos idiomas (`--lang es` y `--lang en`, o artefacto "capturas" de la CI) antes de dar el trabajo por terminado para confirmar que ningún texto se recorte, y actualizar `docs/capturas/` + `README.es.md` (español) y `docs/capturas/en/` + `README.md` (inglés) si cambió lo que muestran.
- Los hilos secundarios usan `app.schedule()` para actualizar la UI en el hilo principal de Tk.
- **Soporte bilingüe obligatorio (español e inglés):** los nombres de variables, comentarios y docstrings del código se mantienen en español, pero **toda nueva funcionalidad o modificación visible debe funcionar en ambos idiomas**:
  - Todo texto de la UI, bandeja, menús o notificaciones debe usar `tr(...)` (`config.py`) y agregarse tanto en `TRANSLATIONS["es"]` como en `TRANSLATIONS["en"]` (`constants.py`) con las mismas claves y placeholders.
  - Si se añaden o modifican acciones predeterminadas, actualizar tanto `AI_ACTIONS` (español) como `AI_ACTIONS_EN` (inglés) en `constants.py` (usando `"preserve_target_language": True` solo en acciones de traducción explícita).
  - Toda invocación a `generate_text()` debe respetar `apply_language` para que la IA responda siempre en el idioma seleccionado por el usuario.
  - Si se documentan nuevas funcionalidades o cambios de uso, actualizar tanto `README.md` (inglés, por defecto) como `README.es.md` (español).

---

## Referencia técnica

### Esquema de `actions.json`
Puedes gestionarlas desde la pestaña **Acciones** en Configuración o editando directamente `actions.json` (`%APPDATA%\Escriba\actions.json` en Windows, `~/Library/Application Support/Escriba/actions.json` en macOS, `~/.config/Escriba/actions.json` en Linux):

```json
[
  {
    "label": "✎  Reescribir",
    "prompt": "Reescribe el siguiente texto para mejorar su claridad y fluidez.",
    "section": "Texto y Contenido",
    "shortcut": "Ctrl+R",
    "auto_replace": false
  }
]
```

* **Variables en prompts:** `{app}`, `{clipboard}`, `{lang}`, `{date}`, `{time}`, `{datetime}` y campos interactivos `{input:Etiqueta}`.
* **`mode`:** `"selection"` (por defecto), `"compose"` (visible sin selección) o `"both"` (ambos).
* **`apps`:** lista opcional de aplicaciones (ej. `["outlook", "code"]`) para mostrar y promover esa acción solo en ellas.
* **`temperature` / `model`:** sobrescribe temperatura (`0.0–2.0`) o modelo para esa acción.
* **`strip_markdown`:** si es `true`, elimina envoltorios ```` ```lang ... ``` ```` de la respuesta.
* **`auto_replace`:** si es `true`, sustituye el texto en la aplicación de origen automáticamente al terminar la generación.

### Claves de `config.json`
Se almacena en `%APPDATA%\Escriba\config.json` (Windows), `~/Library/Application Support/Escriba/config.json` (macOS) o `~/.config/Escriba/config.json` (Linux, con permisos `0600`):

| Clave | Tipo | Descripción |
| --- | --- | --- |
| `api_key_enc` / `api_key_keychain` | string / bool | API Key de Gemini (cifrada con DPAPI en Windows o marcada en Llavero en macOS) |
| `model` | string | Modelo de Gemini seleccionado (por defecto: `gemini-3.5-flash-lite`) |
| `provider` | string | Proveedor principal: `"gemini"` u `"openai"` |
| `fallback_enabled` | boolean | Habilita respaldo automático al proveedor secundario |
| `openai_base_url` / `openai_model` | string | URL base y modelo del proveedor alternativo |
| `openai_api_key_enc` | string | API Key del proveedor alternativo (DPAPI / Llavero) |
| `hotkey` | string | Atajo global personalizado (p. ej. `"Win+Alt+E"`, `"Ctrl+Alt+K"`) |
| `repeat_hotkey` | string | Atajo secundario para repetir la última acción sin abrir menú |
| `streaming` | boolean | Mostrar respuesta mientras se genera (por defecto: `true`) |
| `rich_paste` | boolean | Copiar y pegar Markdown convertido a HTML (por defecto: `false`) |
| `autostart` | boolean | Inicio automático al iniciar sesión (por defecto: `false`) |
| `language` | string | Idioma de la UI y respuestas de IA: `"es"` o `"en"` (auto-detectado al inicio) |
| `action_usage` | object | Contadores de uso para promover acciones frecuentes |
| `recent_prompts` | array | Últimas instrucciones libres ejecutadas en el menú |

### Implementación por plataforma

| Aspecto | Windows | macOS | Linux (X11) |
| --- | --- | --- | --- |
| Atajo global por defecto | `Win+Alt+E` | `⌃⌘E` (`Ctrl+Cmd+E`) | `Ctrl+Alt+E` |
| Portapapeles / Pegado | WinAPI + `keyboard` | Quartz (`CGEvent`) | `pynput` + `xclip` (`wtype` en Wayland) |
| Ventana activa | WinAPI (`AttachThreadInput`) | `NSWorkspace` / `NSRunningApplication` | `xdotool` |
| Secretos | DPAPI (`crypt32.dll`) | Llavero (`security -i`) | `config.json` (`chmod 0600`) |
| Inicio automático | Registro `HKCU\...\Run` | `~/Library/LaunchAgents/com.cgarciagl.escriba.plist` | `~/.config/autostart/escriba.desktop` |

### Pruebas, compilación y publicación

#### Requisitos de desarrollo

```bash
pip install -r requirements-dev.txt
```

#### Ejecutar pruebas

```bash
# Tests de lógica (multiplataforma)
python -m pytest -q -rf --ignore=tests/test_ui.py

# Tests de interfaz (requiere Tk real; en Linux sin display usa xvfb-run -a)
python -m pytest -q -rf tests/test_ui.py
```

#### Compilar ejecutable / bundle

```bash
pyinstaller Escriba.spec --clean --noconfirm
```

* En **Windows** genera `dist\Escriba.exe`.
* En **macOS** genera `dist/Escriba.app`.
* En **Linux** genera `dist/Escriba`.

#### Publicar una nueva versión

Al subir un tag con prefijo `v*` (por ejemplo `git tag v0.0.6 && git push origin v0.0.6`), el workflow [`.github/workflows/tests.yml`](.github/workflows/tests.yml) ejecuta todas las pruebas, compila los tres binarios y crea automáticamente la Release en GitHub con `Escriba.exe`, `Escriba-macos.zip` y `Escriba-linux.tar.gz`.

### Estructura del proyecto

```text
escriba/
├── escriba.py          # Orquestador principal: hotkey, tray, captura y ciclo de vida
├── Escriba.spec        # Especificación PyInstaller (Windows .exe, macOS .app, Linux)
├── constants.py        # Versión, rutas base, modelos y acciones predeterminadas
├── config.py           # ConfigManager (thread-safe, escritura atómica, DPAPI/Llavero)
├── actions.py          # Validación, guardado, filtrado y variables de actions.json
├── history.py          # Historial en memoria acotado y seguro entre hilos
├── ai_clients.py       # GeminiClient, OpenAICompatibleClient, SSE streaming y reintentos
├── plataforma.py       # Capa de abstracción Windows / macOS / Linux
├── hotkey.py           # Windows: RegisterHotKey configurable y helpers de teclado
├── startup.py          # Windows: arranque automático en Registro HKCU
├── macos.py            # macOS: pynput, Quartz, NSWorkspace, LaunchAgent y Llavero
├── linux_platform.py   # Linux (X11): pynput, xdotool y autostart .desktop
├── tray.py             # Ícono y menú dinámico en bandeja / barra de menús
├── ui_windows.py       # Fachada de módulos de interfaz
├── ui_common.py        # Paleta oscura, estilos ttk, DPI awareness y notificaciones
├── ui_menu.py          # Paleta de comandos con scroll, modo redacción y frecuentes
├── ui_result.py        # Ventana de resultados: streaming, diff, Markdown y ajuste
├── ui_config.py        # Configuración por pestañas y editor visual de acciones
├── tests/              # Suite automatizada con pytest (lógica + Tk)
├── tools/capturas.py   # Generación automática de capturas para documentación
└── .github/workflows/  # CI/CD: tests, builds y publicación de Releases
```
