# ⚡ Escriba — Asistente de Texto con IA para Windows

Asistente nativo que se ejecuta en segundo plano con ícono en la bandeja del sistema. Con solo presionar **Ctrl+Shift+Space** sobre cualquier texto seleccionado, muestra un menú flotante de acciones de IA. El resultado se presenta en una ventana editable con opción de sustituir el texto original o copiarlo al portapapeles.

Funciona **sin configuración previa**: usa Pollinations AI de forma gratuita por defecto. Si se configura una API Key de Google Gemini, la usa con fallback automático a Pollinations si falla.

## 🎨 Stack

| Componente              | Librería / Tecnología                                                 |
| ----------------------- | --------------------------------------------------------------------- |
| UI / Tema               | `ttkbootstrap` (tema **vapor**)                                       |
| System Tray             | `pystray` + `Pillow`                                                  |
| Hotkey global           | `keyboard`                                                            |
| Portapapeles            | `pyperclip`                                                           |
| Foco de ventana         | `ctypes` (WinAPI: `AttachThreadInput`, `SetForegroundWindow`)         |
| Inicio con Windows      | `winreg` (HKCU Run)                                                   |
| API principal           | `requests` → Google Gemini 2.x Flash (auto-detección de modelo)       |
| API gratuita (fallback) | `requests` → [Pollinations AI](https://pollinations.ai) (sin API Key) |
| Persistencia            | `config.json` local (generado automáticamente)                        |
| Compilación             | PyInstaller (`Escriba.spec`)                                          |

## 🚀 Instalación

```bash
pip install -r requirements.txt
```

## ▶️ Ejecución

```bash
python escriba.py
```

Al primer arranque se crea `config.json` con inicio automático con Windows activado. No se requiere API Key para comenzar a usarlo.

## ⌨️ Uso

1. Selecciona cualquier texto en cualquier aplicación.
2. Presiona **Ctrl+Shift+Space**.
3. En el menú flotante elige una acción:
   - ✍️ **Reescribir** — Mejora claridad y fluidez
   - 💡 **Explicar** — Explicación detallada y concisa
   - 📐 **Extender** — Amplía con más detalles
   - 📋 **Resumir** — Resumen ejecutivo con puntos clave
   - 🗄️ **Fix SQL** — Formatea consultas SQL
   - 🔍 **Explicar Código** — Análisis paso a paso del código
4. Mientras procesa se muestra una ventana con barra de progreso animada.
5. El resultado aparece en una ventana editable:
   - **⬅️ Sustituir** — reemplaza el texto original vía Ctrl+V
   - **📋 Copiar** — copia al portapapeles
   - **✕ Cerrar** — descarta el resultado

## 🔑 API Key de Gemini (opcional)

Para usar Google Gemini en lugar de Pollinations, configura tu clave desde el ícono del tray → **Configuración**.  
Obtén tu clave en: <https://aistudio.google.com/apikey>

La app detecta automáticamente el mejor modelo Gemini disponible para tu clave (gemini-2.5-flash, gemini-2.0-flash, etc.).

## 📦 Compilar a .exe

```bash
pyinstaller Escriba.spec --clean --noconfirm
```

El ejecutable se genera en `dist\Escriba.exe`.

## 🗂️ Estructura

```text
escriba/
├── escriba.py          # Código principal (archivo único)
├── Escriba.spec        # Configuración de compilación PyInstaller
├── config.json         # Configuración (se crea automáticamente)
├── requirements.txt    # Dependencias Python
├── escriba.ico         # Ícono de la aplicación
└── README.md           # Este archivo
```

## ⚙️ Configuración (`config.json`)

```json
{
  "api_key": "tu-api-key-de-gemini-opcional",
  "autostart": true
}
```

Se genera automáticamente al primer arranque con `autostart: true`. Se puede editar desde el menú **Configuración** del ícono en la bandeja del sistema.
