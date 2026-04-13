# ✍️ Escriba — Asistente de Texto con IA para Windows

Aplicación nativa de escritorio que proporciona asistencia de IA integrada directamente en tu flujo de escritura. Funciona de manera completamente desatendida en la bandeja del sistema y se activa al presionar una combinación de teclas global, sin interferir con ninguna otra aplicación.

**Escoge una de seis acciones de IA** sobre cualquier texto seleccionado: reescribir, explicar, extender, resumir, corregir SQL o analizar código. Los resultados se presentan en una ventana editable e interactiva que permite sustituir el texto original con un clic o copiar al portapapeles.

**Funciona sin configuración**: por defecto utiliza [Pollinations AI](https://pollinations.ai) de forma completamente gratuita. Opcionalmente, configura una clave de Google Gemini para usar el modelo oficial con fallback automático a Pollinations si algo falla.

## 🎯 Características

- ⌨️ **Hotkey global** (`Ctrl+Shift+Space`) que funciona en cualquier aplicación
- 🤖 **Seis acciones de IA**: reescribir, explicar, extender, resumir, fix SQL, analizar código
- 📋 **Sin API Key requerida** — usa Pollinations AI gratis por defecto
- 🔄 **Fallback automático** — intenta Gemini primero; si falla, usa Pollinations
- 🎨 **Interfaz moderna** — tema Vapor con menú flotante y ventana de resultados
- 📌 **Bandeja del sistema** — se ejecuta silenciosamente en segundo plano
- ⚡ **Captura inteligente** — extrae el texto seleccionado sin dejar rastro en el portapapeles
- 🚀 **Inicio automático** — Se añade a HKCU Run al primer arranque
- 📦 **Compilado a .exe** — distribuzione lista para usar sin Python

## 🛠️ Stack Técnico

| Aspecto                 | Tecnología                                                      |
| ----------------------- | --------------------------------------------------------------- |
| **Interfaz gráfica**    | `ttkbootstrap` (tema Vapor)                                     |
| **Bandeja del sistema** | `pystray` + `Pillow`                                            |
| **Hotkey global**       | `keyboard` (supresión de teclas garantizada)                    |
| **Portapapeles**        | `pyperclip`                                                     |
| **Foco de ventana**     | `ctypes` (WinAPI: `AttachThreadInput`, `SetForegroundWindow`)   |
| **Inicio con Windows**  | `winreg` (escritura en HKCU\Software\Microsoft\Windows\Run)     |
| **IA principal**        | `requests` → Google Gemini 2.x Flash (auto-detección de modelo) |
| **IA gratuita**         | `requests` → Pollinations AI (fallback sin API Key)             |
| **Configuración**       | `config.json` (generado automáticamente en primer arranque)     |
| **Distribución**        | PyInstaller (`Escriba.spec`)                                    |

## 🚀 Inicio Rápido

### Instalación

1. Clone o descargue el repositorio:

```bash
git clone https://github.com/cgarciagl/escriba.git
cd escriba
```

1. Instale las dependencias:

```bash
pip install -r requirements.txt
```

### Ejecución

```bash
python escriba.py
```

Al primer arranque, la aplicación:

- Crea automáticamente `config.json` con la configuración predeterminada
- Se registra para iniciar automáticamente al abrir sesión en Windows
- Muestra un banner de bienvenida y se coloca en la bandeja del sistema

No require API Key para funcionar. Pulsa con el botón derecho en el ícono de la bandeja para acceder a configuración y otras opciones.

## ⌨️ Cómo Usar

1. **Selecciona** cualquier texto en cualquier aplicación (navegador, editor, chat, etc.)
2. **Presiona** `Ctrl+Shift+Space` — aparecerá un menú flotante junto al cursor
3. **Elige** una de estas seis acciones:
   - ✍️ **Reescribir** — Mejora la claridad, fluidez y gramática
   - 💡 **Explicar** — Proporciona una explicación detallada pero concisa
   - 📐 **Extender** — Amplía el texto con más detalles y profundidad
   - 📋 **Resumir** — Resumen ejecutivo con los puntos clave
   - 🗄️ **Fix SQL** — Valida y formatea consultas SQL
   - 🔍 **Explicar Código** — Análisis paso a paso del funcionamiento
4. **Procesa** — Se muestra una ventana con barra de progreso animada
5. **Interactúa** — El resultado aparece en una ventana editable:
   - **⬅️ Sustituir** — Reemplaza el texto original automáticamente
   - **📋 Copiar** — Copia el resultado al portapapeles
   - **✕ Cerrar** — Descarta el resultado y cierra la ventana

## 🔑 Configuración de API

### Usa Google Gemini (recomendado)

1. Obtén una API Key gratuita en: <https://aistudio.google.com/apikey>
2. Abre Escriba → ícono en bandeja del sistema → **Configuración**
3. Pega tu clave y guarda

La aplicación detecta automáticamente el mejor modelo Gemini disponible (gemini-2.5-flash, gemini-2.0-flash, etc.) y lo usa de forma inteligente.

### Modos de operación

| Escenario                      | Comportamiento                                        |
| ------------------------------ | ----------------------------------------------------- |
| Sin API Key configurada        | Usa Pollinations AI (gratuito, sin registro)          |
| API Key de Gemini válida       | Usa Gemini con fallback a Pollinations si falla       |
| API Key inválida o sin crédito | Fallback automático a Pollinations sin interrupciones |
| Sin conexión a internet        | La aplicación lo notifica en la ventana de resultado  |

## 📦 Compilar a Ejecutable

Para generar un `.exe` distribuible sin requerir Python:

```bash
pyinstaller Escriba.spec --clean --noconfirm
```

El ejecutable se genera en `dist\Escriba.exe` listo para ejecutar o distribuir.

## 🗂️ Estructura del Proyecto

```text
escriba/
├── escriba.py          # Punto de entrada principal — orquesta hotkey, tray, UI y IA
├── Escriba.spec        # Configuración de PyInstaller para compilación
├── requirements.txt    # Dependencias Python (pip install -r requirements.txt)
├── config.json         # Configuración del usuario (se crea automáticamente)
├── constants.py        # Constantes y rutas de la aplicación
├── config.py           # Gestor de persistencia de configuración
├── startup.py          # Gestor de inicio automático con Windows
├── hotkey.py           # Captura del hotkey global (Ctrl+Shift+Space)
├── tray.py             # Ícono y menú de bandeja del sistema
├── ui_windows.py       # Componentes UI (menú flotante, ventana config, etc.)
├── ai_clients.py       # Clientes de IA (Gemini, Pollinations, fallback)
├── build/              # Carpeta de compilación (genera pyinstaller)
└── README.md           # Este archivo
```

## ⚙️ Configuración (`config.json`)

Archivo generado automáticamente en el primer arranque con el siguiente contenido:

```json
{
  "api_key": "",
  "autostart": true
}
```

### Parámetros

| Clave       | Tipo    | Descripción                                                                 |
| ----------- | ------- | --------------------------------------------------------------------------- |
| `api_key`   | string  | Clave de API de Google Gemini (opcional, deja vacío para usar Pollinations) |
| `autostart` | boolean | Si es `true`, la app se inicia automáticamente con Windows                  |

### Edición de configuración

Modifica la configuración de dos formas:

1. **Desde la UI** — Abre Escriba → ícono de bandeja → **Configuración**
2. **Manual** — Edita directamente `config.json` en la carpeta de la aplicación

Los cambios se aplican inmediatamente sin necesidad de reiniciar.

## 🔧 Arquitectura Interna

### Módulos principales

- **`escriba.py`** — Clase `EscribaApp` que orquesta toda la aplicación. Gestiona el mainloop de Tkinter, la conexión entre hotkey y UI, y el ciclo de vida.
- **`hotkey.py`** — `HotkeyManager` que registra el hotkey global `Ctrl+Shift+Space` sin permitir que la tecla filtre a otras aplicaciones.
- **`tray.py`** — `TrayIconManager` que crea y gestiona el ícono en la bandeja del sistema con menú contextual.
- **`ui_windows.py`** — Componentes de interfaz: `FloatingMenu` (menú flotante), `ResultWindow` (ventana de resultados), `ConfigWindow` (diálogo de configuración).
- **`ai_clients.py`** — Clientes HTTP para `GeminiClient` (Google) y `PollutionsClient` con lógica de fallback automático.
- **`config.py`** — Gestor de persistencia que lee y escribe `config.json`.
- **`startup.py`** — Registra/desregistra la app en la lista de inicio automático de Windows via `winreg`.

### Flujo de ejecución

```text
1. EscribaApp.run() inicia
2. ConfigManager.load() lee config.json
3. TrayIconManager.start() crea ícono en bandeja
4. HotkeyManager.start() registra Ctrl+Shift+Space
5. Espera presión del hotkey...
6. Al presionar Ctrl+Shift+Space:
   └─ Captura texto del portapapeles vía Ctrl+C
   └─ Muestra FloatingMenu en posición del cursor
   └─ Usuario selecciona acción
   └─ Envía petición a Gemini o Pollinations
   └─ Muestra ResultWindow con respuesta
   └─ Usuario gestiona resultado (sustituir, copiar, cerrar)
```

## 📝 Notas de Desarrollo

- **Archivo único principal**: Toda la lógica reside en `escriba.py` y módulos complementarios. No se crean dinámicamente nuevos módulos.
- **Tema UI**: Se usa el tema `vapor` de `ttkbootstrap` para una estética moderna oscura.
- **Supresión de hotkey**: El hotkey nunca filtra a otras aplicaciones gracias al parámetro `suppress=True` de la librería `keyboard`.
- **Captura inteligente**: La aplicación minimiza la contaminación del portapapeles: guarda lo anterior, ejecuta `Ctrl+C`, y restaura si es necesario.
- **Multihilo**: Las operaciones de IA y el hotkey se ejecutan en hilos separados para no bloquear la UI.

## 📄 Licencia y Créditos

Proyecto de escritorio independiente. Utiliza Gemini 2.x Flash (Google) y Pollinations AI (código abierto) para procesamiento de texto mediante IA.
