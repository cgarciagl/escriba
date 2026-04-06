# ⚡ Escriba — Asistente de Texto con IA para Windows

Clon nativo de BoltAI/Copilot que se ejecuta en segundo plano con icono en la bandeja del sistema. Intercepta **Ctrl+Shift+M** para mostrar un menú flotante de IA, procesa texto seleccionado usando la API de Gemini 1.5 Flash, y reemplaza el resultado simulando pulsaciones de teclado.

## 🎨 Stack

| Componente | Librería |
|---|---|
| UI / Tema | `ttkbootstrap` (tema **vapor**) |
| System Tray | `pystray` + `Pillow` |
| Automatización | `keyboard`, `pyperclip`, `pyautogui` |
| API | `requests` → Google Gemini 1.5 Flash |
| Persistencia | `config.json` local |

## 🚀 Instalación

```bash
pip install -r requirements.txt
```

## ▶️ Ejecución

```bash
python escriba.py
```

> **Nota:** La primera vez se abrirá la ventana de configuración para ingresar tu API Key de Gemini.
> Obtén tu clave en: https://aistudio.google.com/apikey

## ⌨️ Uso

1. Selecciona cualquier texto en cualquier aplicación.
2. Presiona **Ctrl+Shift+M**.
3. Elige una acción del menú flotante:
   - ✍️ **Reescribir** — Mejora claridad y fluidez
   - 💡 **Explicar** — Explicación detallada y concisa
   - 📐 **Extender** — Amplía con más detalles
   - 📋 **Resumir** — Resumen ejecutivo con puntos clave
   - 🗄️ **Fix SQL** — Formatea consultas SQL
   - 🔍 **Explicar Código** — Análisis paso a paso del código
4. El resultado reemplaza automáticamente el texto seleccionado.

## 📦 Compilar a .exe

```bash
pyinstaller --noconsole --onefile --icon=escriba.ico --name=Escriba escriba.py
```

El ejecutable se generará en la carpeta `dist/`.

## 🗂️ Estructura

```
escriba/
├── escriba.py          # Código principal (archivo único)
├── config.json         # Configuración (se crea automáticamente)
├── requirements.txt    # Dependencias Python
└── README.md           # Este archivo
```

## ⚙️ Configuración

La app usa un archivo `config.json` junto al ejecutable:

```json
{
  "api_key": "tu-api-key-de-gemini"
}
```

Se puede editar manualmente o desde el menú **Configuración** del icono en la bandeja del sistema.
