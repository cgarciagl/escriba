# ✍️ Escriba — Asistente de Texto con IA para Windows

Aplicación nativa de escritorio que proporciona asistencia de IA integrada directamente en tu flujo de escritura. Funciona de manera completamente desatendida en la bandeja del sistema y se activa al presionar una combinación de teclas global, sin interferir con ninguna otra aplicación.

**Escoge una de diez acciones de IA** (o redacta tu propio prompt personalizado) sobre cualquier texto seleccionado: reescribir, explicar, extender, resumir, mejorar correos, traducir (español/inglés), corregir SQL, refactorizar o explicar código. Los resultados se presentan en una ventana editable e interactiva que permite sustituir el texto original con un clic, copiar al portapapeles o regenerar la respuesta.

**Impulsado por Google Gemini**: utiliza la API oficial de Google Gemini con modelos optimizados de alta velocidad como `gemini-3.5-flash-lite`. Incorpora detección y selección dinámica de modelos, así como reintentos automáticos inteligentes con retroceso exponencial ante saturación temporal o límites de cuota.

## 🎯 Características

- ⌨️ **Hotkey global** (`Win+Alt+E`) que funciona en cualquier aplicación sin filtrado de teclas
- 🤖 **10 acciones de IA predefinidas**: categorizadas en Texto y Contenido, Idiomas y Herramientas para Desarrolladores
- ⌨️ **Atajos de teclado directos**: cada acción en el menú flotante cuenta con su propio atajo rápido (`Ctrl+R`, `Ctrl+E`, `Ctrl+1`, `Ctrl+D`, etc.)
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
| **Configuración**       | `config.json` (gestión mediante `ConfigManager` con caché en memoria)                  |
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

- Crea automáticamente `config.json` con la configuración predeterminada
- Registra el inicio automático con Windows (si está habilitado en configuración)
- Muestra un banner de bienvenida y se aloja en la bandeja del sistema

> **Nota:** Para procesar solicitudes con IA, es necesario configurar una API Key de Google Gemini. Haz clic derecho en el ícono de Escriba en la bandeja del sistema y selecciona **Configuración**.

## ⌨️ Cómo Usar

1. **Selecciona** cualquier texto en cualquier aplicación (navegador, editor, chat, terminal, etc.).
2. **Presiona** `Win+Alt+E` — aparecerá un menú flotante centrado en pantalla.
3. **Elige** una acción (con clic o mediante su atajo de teclado):

   ### 📝 Texto y Contenido
   - ✎ **Reescribir** (`Ctrl+R`) — Mejora la claridad, fluidez y gramática conservando el sentido.
   - ◉ **Explicar** (`Ctrl+E`) — Proporciona una explicación detallada, estructurada y concisa.
   - ⇲ **Extender** (`Ctrl+X`) — Amplía el texto de forma coherente sin añadir información inventada.
   - ≡ **Resumir** (`Ctrl+S`) — Genera un resumen ejecutivo destacando los puntos esenciales.
   - ✉ **Mejorar Correo** (`Ctrl+M`) — Optimiza el correo buscando tono profesional, cortesía y claridad.

   ### 🌐 Idiomas
   - ◐ **Traducir al español** (`Ctrl+1`) — Traduce fielmente el texto al español sin comentarios adicionales.
   - ◑ **Traducir al inglés** (`Ctrl+2`) — Traduce fielmente el texto al inglés sin comentarios adicionales.

   ### 💻 Para Desarrolladores
   - ▤ **Fix SQL** (`Ctrl+D`) — Valida y formatea consultas SQL con estructura compacta y seccionada.
   - ✦ **Refactorizar Código** (`Ctrl+F`) — Aplica principios de Clean Code, reduce anidamiento y renombra variables.
   - ⊙ **Explicar Código** (`Ctrl+P`) — Análisis paso a paso de la lógica y funcionamiento del código.

   ### ✏️ Prompt Personalizado
   - Haz clic en **Crear prompt personalizado** para abrir un diálogo donde podrás introducir cualquier instrucción libre sobre el texto seleccionado.

4. **Procesamiento** — Se muestra una ventana flotante con barra de progreso mientras Gemini genera la respuesta. Si el modelo experimenta saturación temporal, la ventana mostrará el reintento automático.
5. **Interactúa con el resultado** — En la ventana de respuesta podrás:
   - **⬅️ Sustituir texto seleccionado** — Reemplaza automáticamente el texto seleccionado en la aplicación original.
   - **🔄 Volver a generar** — Solicita una nueva respuesta a Gemini con el mismo prompt.
   - **📋 Copiar al portapapeles** — Copia el texto generado.
   - **✕ Cerrar** — Cierra la ventana y descarta el resultado.

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
pyinstaller Escriba.spec --clean --noconfirm
```

El ejecutable se generará en `dist\Escriba.exe`.

## 🗂️ Estructura del Proyecto

```text
escriba/
├── escriba.py          # Punto de entrada principal — orquesta hotkey, tray, UI y ciclo de vida
├── Escriba.spec        # Especificación de PyInstaller para compilar el ejecutable
├── requirements.txt    # Dependencias de Python (pip install -r requirements.txt)
├── config.json         # Configuración persistente del usuario (creado automáticamente)
├── constants.py        # Constantes, modelos Gemini y definición de las 10 acciones de IA
├── config.py           # Gestor de persistencia de configuración (ConfigManager)
├── startup.py          # Gestor de inicio automático con Windows vía registro HKCU (StartupManager)
├── hotkey.py           # Registro de hotkey global (Win+Alt+E) y utilidades de teclado
├── tray.py             # Ícono y menú de bandeja del sistema vía pystray
├── ui_windows.py       # Ventanas de la interfaz (FloatingMenu, ResultWindow, ConfigWindow, etc.)
├── ai_clients.py       # Cliente GeminiClient con reintentos exponenciales y consulta de modelos
├── tests/              # Suite de pruebas automatizadas con pytest
├── build/              # Archivos temporales generados por PyInstaller
├── dist/               # Contiene el ejecutable final Escriba.exe
└── README.md           # Documentación principal del proyecto
```

## ⚙️ Configuración (`config.json`)

Archivo generado automáticamente en el primer arranque con la configuración por defecto:

```json
{
  "api_key": "",
  "model": "gemini-3.5-flash-lite",
  "autostart": true
}
```

### Parámetros

| Clave       | Tipo    | Descripción                                                                          |
| ----------- | ------- | ------------------------------------------------------------------------------------ |
| `api_key`   | string  | Clave de API de Google Gemini (requerida para realizar consultas)                    |
| `model`     | string  | Modelo de Google Gemini seleccionado (por defecto: `gemini-3.5-flash-lite`)          |
| `autostart` | boolean | Si es `true`, la app se registra para iniciar automáticamente al iniciar sesión en Windows |

### Edición de configuración

Puedes modificar la configuración de dos formas:

1. **Desde la UI** — Haz clic derecho en el ícono de la bandeja de Escriba → **Configuración**.
2. **Manual** — Edita el archivo `config.json` en la carpeta raíz de la aplicación.

Los cambios guardados desde la UI se aplican inmediatamente.

## 🔧 Arquitectura Interna

### Módulos principales

- **`escriba.py`** — Clase `EscribaApp`. Orquesta el mainloop de Tkinter, la conexión entre el hotkey global y las ventanas, y el ciclo de vida de la aplicación.
- **`hotkey.py`** — `HotkeyManager`. Registra `Win+Alt+E` a nivel de sistema operativo utilizando la función WinAPI `RegisterHotKey`, asegurando la captura sin conflictos ni fugas de teclas. Incluye funciones de asistencia de teclado para enviar secuencias seguras de `Ctrl+C` y `Ctrl+V`.
- **`tray.py`** — `TrayIconManager`. Crea el ícono en la bandeja del sistema con opciones para abrir Configuración, ver información o salir.
- **`ui_windows.py`** — Componentes de interfaz gráfica construidos con `ttkbootstrap` y `tkinter`: `FloatingMenu`, `ResultWindow`, `ConfigWindow`, `ThinkingWindow`, `CustomPromptWindow` y `TooltipNotification`.
- **`ai_clients.py`** — Clase `GeminiClient` y función `generate_with_fallback`. Realiza peticiones a la API REST de Google Gemini, detecta errores transitorios (`is_retryable_error`), aplica pausas con retroceso exponencial y consulta modelos habilitados.
- **`config.py`** — `ConfigManager`. Carga y guarda la configuración en `config.json` con soporte para caché en memoria.
- **`startup.py`** — `StartupManager`. Modifica la clave de registro `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` para habilitar o deshabilitar el arranque automático.

### Flujo de ejecución

```text
1. EscribaApp.run() inicia la aplicación
2. ConfigManager.load() lee o inicializa config.json
3. StartupManager asegura el registro en Windows según configuración
4. TrayIconManager.start() coloca el ícono en la bandeja
5. HotkeyManager.start() registra el atajo global Win+Alt+E
6. Al presionar Win+Alt+E:
   └─ Captura el texto seleccionado mediante simulación segura de Ctrl+C
   └─ Despliega FloatingMenu con las 10 acciones organizadas y la opción de prompt libre
   └─ El usuario escoge una acción o introduce un prompt personalizado
   └─ Se muestra ThinkingWindow con indicador de progreso
   └─ Se envía la solicitud a Google Gemini (con reintentos si hay sobrecarga)
   └─ Se abre ResultWindow con el texto generado
   └─ El usuario puede sustituir en la app original, volver a generar, copiar o cerrar
```

## 📝 Notas de Desarrollo

- **Diseño modular y limpio**: La lógica está distribuida en módulos cohesivos con responsabilidades bien delimitadas.
- **Tema UI**: Utiliza el tema oscuro moderno `vapor` de `ttkbootstrap`.
- **Captura no invasiva**: Al pulsar el atajo, el contenido anterior del portapapeles es preservado y restaurado para evitar alterar el historial del usuario.
- **Concurrencia multihilo**: Las peticiones HTTP hacia Gemini y el monitoreo del hotkey corren en hilos dedicados para garantizar que la interfaz gráfica permanezca siempre fluida y responsiva.

## 📄 Licencia y Créditos

Proyecto de escritorio independiente para Windows. Desarrollado con Python, `ttkbootstrap` y la API de Google Gemini (Google AI Studio).

