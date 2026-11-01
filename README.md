# ✍️ Escriba — Asistente de Texto con IA para Windows

Aplicación nativa de escritorio que proporciona asistencia de IA integrada directamente en tu flujo de escritura. Funciona de manera completamente desatendida en la bandeja del sistema y se activa al presionar una combinación de teclas global, sin interferir con ninguna otra aplicación.

**Escoge una de diez acciones de IA** (personalizables, o redacta tu propio prompt) sobre cualquier texto seleccionado: reescribir, explicar, extender, resumir, mejorar correos, traducir (español/inglés), corregir SQL, refactorizar o explicar código. Los resultados se presentan en una ventana editable e interactiva que permite sustituir el texto original con un clic, copiar al portapapeles o regenerar la respuesta.

**Impulsado por Google Gemini**: utiliza la API oficial de Google Gemini con modelos optimizados de alta velocidad como `gemini-3.5-flash-lite`. Incorpora detección y selección dinámica de modelos, así como reintentos automáticos inteligentes con retroceso exponencial ante saturación temporal o límites de cuota. Opcionalmente puede usar (o recurrir a) cualquier **servidor compatible con OpenAI**, como Ollama en local.

## 🎯 Características

- ⌨️ **Hotkey global** (`Win+Alt+E`) que funciona en cualquier aplicación sin filtrado de teclas
- 🤖 **10 acciones de IA predefinidas**: categorizadas en Texto y Contenido, Idiomas y Herramientas para Desarrolladores
- 🧩 **Acciones personalizables**: edita, agrega o quita acciones (prompt, sección y atajo) en `actions.json`, sin recompilar
- ⌨️ **Atajos de teclado directos**: cada acción en el menú flotante cuenta con su propio atajo rápido (`Ctrl+R`, `Ctrl+E`, `Ctrl+1`, `Ctrl+D`, etc.)
- 📡 **Respuesta en streaming**: el texto aparece en la ventana de resultado conforme se genera
- 🔀 **Proveedor alternativo**: Ollama, OpenAI, OpenRouter o LM Studio vía API compatible con OpenAI, como principal o como respaldo automático
- 🕘 **Historial**: las últimas 10 respuestas de la sesión, accesibles desde el menú de la bandeja
- ✏️ **Prompt personalizado**: ventana dedicada para ingresar instrucciones libres sobre el texto seleccionado
- ⚡ **Google Gemini Oficial**: soporte para modelos Flash (`gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-2.5-flash`, etc.) con descarga dinámica de modelos disponibles
- 🔄 **Reintentos automáticos**: gestión transparente de saturación de modelos y rate limits (HTTP 429, 503) con retroceso exponencial
- 🎨 **Interfaz moderna**: tema Vapor (`ttkbootstrap`) con animaciones suaves de entrada, menú flotante y ventana de resultados
- 📌 **Bandeja del sistema**: se ejecuta silenciosamente en segundo plano (`pystray`)
- ⚡ **Captura inteligente**: extrae el texto seleccionado vía portapapeles y restaura el portapapeles original
- 🚀 **Inicio automático configurable**: opción para iniciar automáticamente junto a Windows (`HKCU\...\Run`)
- 📦 **Compilado a .exe**: distribución ejecutable lista para usar sin requerir instalación previa de Python

## 🛠️ Stack Técnico

| Aspecto                 | Tecnología                                                                             |
| ----------------------- | -------------------------------------------------------------------------------------- |
| **Interfaz gráfica**    | `ttkbootstrap` (tema Vapor)                                                            |
| **Bandeja del sistema** | `pystray` + `Pillow`                                                                   |
| **Hotkey global**       | WinAPI (`RegisterHotKey` vía `ctypes`) + `keyboard` (envío limpio de `Ctrl+C` y `Ctrl+V`) |
| **Portapapeles**        | `pyperclip`                                                                            |
| **Foco de ventana**     | `ctypes` (WinAPI: `AttachThreadInput`, `SetForegroundWindow`, `BringWindowToTop`)      |
| **Inicio con Windows**  | `winreg` (escritura en `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`)           |
| **Motor de IA**         | `requests` → Google Gemini API (`v1beta`) con reintentos y retroceso exponencial       |
| **Configuración**       | `%APPDATA%\Escriba\config.json` (`ConfigManager`, API Key cifrada con DPAPI)           |
| **Distribución**        | PyInstaller (`Escriba.spec`, ejecutable monousuario sin consola)                       |

## 🚀 Inicio Rápido

### Instalación

1. Clone o descargue el repositorio:

```bash
git clone https://github.com/cgarciagl/escriba.git
cd escriba
```

2. Instale las dependencias:

```bash
pip install -r requirements.txt
```

### Ejecución

```bash
python escriba.py
```

Al primer arranque, la aplicación:

- Crea automáticamente `%APPDATA%\Escriba\config.json` con la configuración predeterminada (si existía un `config.json` junto al ejecutable, lo migra)
- El inicio automático con Windows viene **desactivado**; se activa desde la ventana de Configuración
- Muestra un banner de bienvenida y se aloja en la bandeja del sistema

> **Nota:** Para procesar solicitudes con IA, es necesario configurar una API Key de Google Gemini. Haz clic derecho en el ícono de Escriba en la bandeja del sistema y selecciona **Configuración**.

## ⌨️ Cómo Usar

1. **Selecciona** cualquier texto en cualquier aplicación (navegador, editor, chat, terminal, etc.).
2. **Presiona** `Win+Alt+E` — aparecerá un menú flotante centrado en pantalla.
3. **Elige** una acción (con clic o mediante su atajo de teclado):

   ### 📝 Texto y Contenido
   - ✎ **Reescribir** (`Ctrl+R`) — Mejora la claridad, fluidez y gramática conservando el sentido.
   - ◉ **Explicar** (`Ctrl+E`) — Proporciona una explicación detallada, estructurada y concisa.
   - ⇲ **Extender** (`Ctrl+L`) — Amplía el texto de forma coherente sin añadir información inventada.
   - ≡ **Resumir** (`Ctrl+B`) — Genera un resumen ejecutivo destacando los puntos esenciales.
   - ✉ **Mejorar Correo** (`Ctrl+M`) — Optimiza el correo buscando tono profesional, cortesía y claridad.

   ### 🌐 Idiomas
   - ◐ **Traducir al español** (`Ctrl+1`) — Traduce fielmente el texto al español sin comentarios adicionales.
   - ◑ **Traducir al inglés** (`Ctrl+2`) — Traduce fielmente el texto al inglés sin comentarios adicionales.

   ### 💻 Para Desarrolladores
   - ▤ **Fix SQL** (`Ctrl+D`) — Valida y formatea consultas SQL con estructura compacta y seccionada.
   - ✦ **Refactorizar Código** (`Ctrl+K`) — Aplica principios de Clean Code, reduce anidamiento y renombra variables.
   - ⊙ **Explicar Código** (`Ctrl+P`) — Análisis paso a paso de la lógica y funcionamiento del código.

   ### ✏️ Prompt Personalizado
   - Haz clic en **Crear prompt personalizado** (o pulsa `Ctrl+Espacio`) para abrir un diálogo donde podrás introducir cualquier instrucción libre sobre el texto seleccionado. Ejecútalo con `Ctrl+Enter`.

   > Los atajos evitan `Ctrl+X`, `Ctrl+S` y `Ctrl+F` por su significado habitual. Puedes cambiarlos en `actions.json`.

4. **Procesamiento** — Se muestra una ventana flotante con barra de progreso hasta que llega el primer fragmento; con streaming activado, la ventana de resultado se abre y el texto aparece mientras se genera. Si el modelo experimenta saturación temporal, la ventana mostrará el reintento automático.
5. **Interactúa con el resultado** — En la ventana de respuesta podrás:
   - **⬅️ Sustituir texto seleccionado** — Reemplaza automáticamente el texto seleccionado en la aplicación original.
   - **🔄 Volver a generar** — Solicita una nueva respuesta a Gemini con el mismo prompt.
   - **📋 Copiar al portapapeles** — Copia el texto generado.
   - **✕ Cerrar** — Cierra la ventana y descarta el resultado.
6. **Historial** — Clic derecho en el ícono de la bandeja → **🕘 Historial** para reabrir una de las últimas respuestas (se guardan solo en memoria y se pierden al cerrar Escriba).

## 🔑 Configuración de API y Modelos

### Obtener API Key de Google Gemini

1. Obtén tu API Key gratuita en: <https://aistudio.google.com/apikey>
2. Abre Escriba → haz clic derecho en el ícono de la bandeja del sistema → **Configuración**.
3. Pega tu API Key y guarda.

### Selección de Modelos

En la ventana de **Configuración** puedes seleccionar el modelo de Gemini:
- **Predeterminado:** `gemini-3.5-flash-lite` (rápido, eficiente y ligero).
- **Lista de modelos:** Incluye `gemini-3.5-flash`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro`, entre otros.
- **Botón "🔄 Actualizar":** Con tu API Key ingresada, consulta dinámicamente la API de Gemini para listar todos los modelos disponibles en tu cuenta.

### Proveedor alternativo (compatible con OpenAI)

En **Configuración → Proveedor alternativo** puedes configurar cualquier servidor con el endpoint `/chat/completions`:

| Servidor   | URL base                         | API Key  |
| ---------- | -------------------------------- | -------- |
| Ollama     | `http://localhost:11434/v1`      | No       |
| LM Studio  | `http://localhost:1234/v1`       | No       |
| OpenAI     | `https://api.openai.com/v1`      | Sí       |
| OpenRouter | `https://openrouter.ai/api/v1`   | Sí       |

- Elige si es el **proveedor principal** o deja Gemini como principal.
- Activa **"Si el proveedor principal falla, usar el otro"** para un respaldo automático. El cambio solo ocurre si el primero no llegó a mostrar texto (no se mezclan respuestas de dos modelos).
- El botón **🔄 Listar** consulta `GET /models` del servidor.

### Acciones personalizadas (`actions.json`)

En **Configuración → General → 📝 Editar acciones** se crea `%APPDATA%\Escriba\actions.json` con las acciones predeterminadas y se abre en tu editor. Los cambios se aplican la próxima vez que abras el menú.

```json
[
  {
    "label": "✎  Reescribir",
    "prompt": "Reescribe el siguiente texto para mejorar su claridad y fluidez. Devuelve ÚNICAMENTE el texto reescrito.",
    "section": "Texto y Contenido",
    "bootstyle": "info-outline",
    "shortcut": "Ctrl+R"
  }
]
```

| Campo       | Obligatorio | Descripción                                                                 |
| ----------- | ----------- | --------------------------------------------------------------------------- |
| `label`     | Sí          | Texto del botón (por convención, icono + dos espacios + nombre)             |
| `prompt`    | Sí          | Instrucciones para la IA (se envían como *system instruction*)              |
| `section`   | No          | Agrupa botones; la primera sección se muestra sin encabezado                |
| `bootstyle` | No          | Estilo de `ttkbootstrap` (`info-outline`, `warning-outline`, `danger-outline`…) |
| `shortcut`  | No          | `Ctrl`/`Alt`/`Shift` + letra, dígito o `F1`–`F12` (p. ej. `Ctrl+Shift+T`)   |

Si el archivo tiene errores, Escriba usa las acciones válidas (o las predeterminadas) y muestra un aviso. **↺ Restaurar predeterminadas** sobrescribe el archivo.

### Gestión de Errores y Reintentos

| Escenario                      | Comportamiento                                                                         |
| ------------------------------ | -------------------------------------------------------------------------------------- |
| Sin API Key configurada        | Notificación flotante indicando que se debe configurar la clave en Configuración      |
| Saturación o límite de tasa (HTTP 429, 503) | Reintentos automáticos con retroceso exponencial (hasta 3 intentos) y notificación visual |
| Error de conexión a internet   | Notificación advirtiendo que no se pudo conectar con los servidores de Google Gemini  |
| Cuota agotada o modelo no válido | Mensaje descriptivo indicando el motivo devuelto por la API                            |

## 📦 Compilar a Ejecutable

Para generar un archivo `.exe` distribuible que no requiere tener Python instalado:

```bash
pip install -r requirements-dev.txt
pyinstaller Escriba.spec --clean --noconfirm
```

### Ejecutar las pruebas

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

El ejecutable se generará en `dist\Escriba.exe`.

## 🗂️ Estructura del Proyecto

```text
escriba/
├── escriba.py          # Punto de entrada principal — orquesta hotkey, tray, UI y ciclo de vida
├── Escriba.spec        # Especificación de PyInstaller para compilar el ejecutable
├── requirements.txt    # Dependencias de ejecución (pip install -r requirements.txt)
├── requirements-dev.txt # Dependencias de desarrollo: pytest y PyInstaller
├── constants.py        # Constantes, modelos y las 10 acciones de IA predeterminadas
├── config.py           # Persistencia de configuración y secretos cifrados (ConfigManager)
├── actions.py          # Carga/validación de acciones personalizadas (actions.json)
├── history.py          # Historial en memoria de las últimas respuestas
├── startup.py          # Gestor de inicio automático con Windows vía registro HKCU (StartupManager)
├── hotkey.py           # Registro de hotkey global (Win+Alt+E) y utilidades de teclado
├── tray.py             # Ícono y menú de bandeja del sistema vía pystray
├── ui_windows.py       # Fachada que reexporta las ventanas de los módulos ui_*
├── ui_common.py        # Paleta, helpers, notificaciones, indicador de progreso y banner
├── ui_menu.py          # Menú flotante y ventana de prompt personalizado
├── ui_result.py        # Ejecución de acciones (streaming) y ventana de resultado
├── ui_config.py        # Ventana de configuración con pestañas
├── ai_clients.py       # Clientes Gemini y OpenAI-compatible, streaming, reintentos y fallback
├── tests/              # Suite de pruebas automatizadas con pytest (también corre en CI)
├── .github/workflows/  # CI: ejecuta los tests en Windows en cada push y PR
├── build/              # Archivos temporales generados por PyInstaller
├── dist/               # Contiene el ejecutable final Escriba.exe
└── README.md           # Documentación principal del proyecto
```

## ⚙️ Configuración (`config.json`)

Archivo generado automáticamente en el primer arranque en `%APPDATA%\Escriba\config.json` (escribible aunque la app esté instalada en `Program Files`), con la configuración por defecto:

```json
{
  "api_key": "",
  "model": "gemini-3.5-flash-lite",
  "autostart": false
}
```

Las demás claves se agregan al guardar desde la ventana de Configuración.

### Parámetros

| Clave       | Tipo    | Descripción                                                                          |
| ----------- | ------- | ------------------------------------------------------------------------------------ |
| `api_key`   | string  | Clave en texto plano. Solo se usa fuera de Windows; en Windows queda vacía y se migra a `api_key_enc` |
| `api_key_enc` | string | Clave de API de Google Gemini cifrada con DPAPI (ligada a tu cuenta de Windows). Se establece desde la UI |
| `model`     | string  | Modelo de Google Gemini seleccionado (por defecto: `gemini-3.5-flash-lite`)          |
| `autostart` | boolean | Si es `true`, la app se registra para iniciar automáticamente al iniciar sesión en Windows |
| `streaming` | boolean | Mostrar la respuesta mientras se genera (por defecto: `true`)                         |
| `provider`  | string  | Proveedor principal: `gemini` (por defecto) u `openai`                                |
| `fallback_enabled` | boolean | Recurrir al otro proveedor si el principal falla (por defecto: `false`)       |
| `openai_base_url` | string | URL base del proveedor alternativo (por defecto: Ollama local)                    |
| `openai_model` | string | Modelo del proveedor alternativo                                                     |
| `openai_api_key_enc` | string | API Key del proveedor alternativo, cifrada con DPAPI (opcional)              |

### Edición de configuración

Puedes modificar la configuración de dos formas:

1. **Desde la UI** — Haz clic derecho en el ícono de la bandeja de Escriba → **Configuración**.
2. **Manual** — Edita `%APPDATA%\Escriba\config.json`. Si escribes la API Key en `api_key` en texto plano, Escriba la cifrará automáticamente la próxima vez que la lea.

Los cambios guardados desde la UI se aplican inmediatamente.

## 🔧 Arquitectura Interna

### Módulos principales

- **`escriba.py`** — Clase `EscribaApp`. Orquesta el mainloop de Tkinter, la conexión entre el hotkey global y las ventanas, y el ciclo de vida de la aplicación.
- **`hotkey.py`** — `HotkeyManager`. Registra `Win+Alt+E` a nivel de sistema operativo utilizando la función WinAPI `RegisterHotKey`, asegurando la captura sin conflictos ni fugas de teclas. Incluye funciones de asistencia de teclado para enviar secuencias seguras de `Ctrl+C` y `Ctrl+V`.
- **`tray.py`** — `TrayIconManager`. Crea el ícono en la bandeja del sistema con opciones para abrir Configuración, ver información o salir.
- **`ui_windows.py`** — Fachada que reexporta la interfaz, repartida en `ui_common.py` (paleta y ventanas pequeñas), `ui_menu.py` (`FloatingMenu`, `CustomPromptWindow`), `ui_result.py` (`ResultWindow`, `run_ai_action` con streaming) y `ui_config.py` (`ConfigWindow`).
- **`ai_clients.py`** — `GeminiClient`, `OpenAICompatibleClient` y `generate_text()`. Envía el prompt como *system instruction*, admite streaming (SSE), detecta errores transitorios (`is_retryable_error`), reintenta con retroceso exponencial y aplica el fallback entre proveedores.
- **`actions.py`** — Lee y valida `actions.json`; convierte atajos como `Ctrl+R` al formato de Tk.
- **`history.py`** — Historial en memoria, acotado y seguro entre hilos.
- **`config.py`** — `ConfigManager`. Carga y guarda la configuración en `%APPDATA%\Escriba\config.json` con caché en memoria, migra la ubicación anterior y cifra la API Key con DPAPI (vía `ctypes`, sin dependencias extra).
- **`startup.py`** — `StartupManager`. Modifica la clave de registro `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` para habilitar o deshabilitar el arranque automático.

### Flujo de ejecución

```text
1. EscribaApp.run() inicia la aplicación
2. ConfigManager.load() lee o inicializa %APPDATA%\Escriba\config.json
3. StartupManager asegura el registro en Windows según configuración
4. TrayIconManager.start() coloca el ícono en la bandeja
5. HotkeyManager.start() registra el atajo global Win+Alt+E
6. Al presionar Win+Alt+E:
   └─ Captura el texto seleccionado mediante simulación segura de Ctrl+C
   └─ Despliega FloatingMenu con las acciones de actions.json (o las predeterminadas) y la opción de prompt libre
   └─ El usuario escoge una acción o introduce un prompt personalizado
   └─ Se muestra ThinkingWindow con indicador de progreso
   └─ Se envía la solicitud al proveedor configurado (reintentos y, si está activo, fallback)
   └─ Con el primer fragmento se abre ResultWindow y el texto aparece en streaming
   └─ La respuesta se guarda en el historial de la sesión
   └─ El usuario puede sustituir en la app original, volver a generar, copiar o cerrar
```

## 📝 Notas de Desarrollo

- **Diseño modular y limpio**: La lógica está distribuida en módulos cohesivos con responsabilidades bien delimitadas.
- **Tema UI**: Utiliza el tema oscuro moderno `vapor` de `ttkbootstrap`.
- **Captura no invasiva**: Al pulsar el atajo, el contenido anterior del portapapeles es preservado y restaurado para evitar alterar el historial del usuario.
- **Concurrencia multihilo**: Las peticiones HTTP hacia Gemini y el monitoreo del hotkey corren en hilos dedicados para garantizar que la interfaz gráfica permanezca siempre fluida y responsiva.

## 📄 Licencia y Créditos

Proyecto de escritorio independiente para Windows. Desarrollado con Python, `ttkbootstrap` y la API de Google Gemini (Google AI Studio).

