"""
Escriba — Constantes globales y definiciones de acciones IA.
"""

import os
import sys


# ─────────────────────────────────────────────────────────────
# Rutas base — funciona tanto en .py como en .exe compilado
# ─────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────
# Constantes de la aplicación
# ─────────────────────────────────────────────────────────────
APP_NAME     = "Escriba"
APP_VERSION  = "0.0.5"
STARTUP_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
if sys.platform == "darwin":
    DEFAULT_HOTKEY = "Ctrl+Cmd+E"
    HOTKEY_PRESETS = ["Ctrl+Cmd+E", "Ctrl+Cmd+Space", "Ctrl+Shift+E", "Ctrl+Alt+E"]
elif sys.platform == "win32":
    DEFAULT_HOTKEY = "Win+Alt+E"
    HOTKEY_PRESETS = ["Win+Alt+E", "Ctrl+Alt+E", "Ctrl+Shift+E", "Win+Shift+E"]
else:
    DEFAULT_HOTKEY = "Ctrl+Alt+E"
    HOTKEY_PRESETS = ["Ctrl+Alt+E", "Ctrl+Shift+E", "Super+Alt+E", "Ctrl+Alt+Space"]

# Carpeta de configuración (escribible aunque la app esté en Program Files,
# /Applications o /usr/local/bin):
#   Windows → %APPDATA%\Escriba
#   macOS   → ~/Library/Application Support/Escriba
#   Linux   → $XDG_CONFIG_HOME/Escriba (o ~/.config/Escriba)
def _config_dir() -> str:
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
    if os.environ.get("APPDATA"):
        return os.path.join(os.environ["APPDATA"], APP_NAME)
    if sys.platform.startswith("linux"):
        xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return os.path.join(xdg, APP_NAME)
    return BASE_DIR


CONFIG_DIR         = _config_dir()
CONFIG_FILE        = os.path.join(CONFIG_DIR, "config.json")
LEGACY_CONFIG_FILE = os.path.join(BASE_DIR, "config.json")  # ubicación usada hasta v1.0.0


# ─────────────────────────────────────────────────────────────
# Google Gemini API
# ─────────────────────────────────────────────────────────────
GEMINI_BASE            = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_DEFAULT_MODEL   = "gemini-3.5-flash-lite"
GEMINI_FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
]


# ─────────────────────────────────────────────────────────────
# Proveedor alternativo compatible con la API de OpenAI
# (Ollama local, OpenAI, OpenRouter, LM Studio, etc.)
# ─────────────────────────────────────────────────────────────
OPENAI_DEFAULT_BASE_URL = "http://localhost:11434/v1"   # Ollama
OPENAI_DEFAULT_MODEL    = "llama3.2"

HISTORY_MAX_ITEMS = 10


# ─────────────────────────────────────────────────────────────
# Acciones de IA PREDETERMINADAS del menú flotante.
# El usuario puede reemplazarlas con %APPDATA%\Escriba\actions.json
# (ver actions.py). Los atajos evitan Ctrl+X/S/F por su significado habitual.
# ─────────────────────────────────────────────────────────────
AI_ACTIONS = [
    {
        "label":        "✎  Reescribir",
        "prompt":       "Reescribe el siguiente texto para mejorar su claridad y fluidez. "
                        "Devuelve ÚNICAMENTE el texto reescrito, sin explicaciones ni comentarios.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+R",
    },
    {
        "label":        "◉  Explicar",
        "prompt":       "Explica de forma detallada pero concisa el siguiente texto. "
                        "Sé claro y estructurado.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+E",
    },
    {
        "label":        "⇲  Extender",
        "prompt":       "Amplía el siguiente texto de forma coherente. Pero sin alucinar ni inventar información. Solo extiende lo que ya está, sin cambiar el sentido original. "
                        "Devuelve ÚNICAMENTE el texto extendido.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+L",
    },
    {
        "label":        "≡  Resumir",
        "prompt":       "Genera un resumen ejecutivo del siguiente texto destacando los puntos clave.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+B",
    },
    {
        "label":        "✉  Mejorar Correo",
        "prompt":       "Mejora el siguiente correo electrónico enfocándote en claridad, profesionalismo y tono adecuado. "
                        "Mantén el contenido esencial y la intención original. "
                        "Devuelve ÚNICAMENTE el correo mejorado, sin explicaciones ni comentarios.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+M",
    },
    {
        "label":        "◐  Traducir al español",
        "prompt":       "Tu tarea es traducir el siguiente texto al español. "
                        "Devuelve ÚNICAMENTE el texto traducido, sin explicaciones, sin comentarios, sin aclaraciones. "
                        "Solo la traducción exacta:\n\n",
        "bootstyle":    "warning-outline",
        "section":      "Idiomas",
        "shortcut":     "Ctrl+1",
    },
    {
        "label":        "◑  Traducir al inglés",
        "prompt":       "Your task is to translate the following text to English. "
                        "Return ONLY the translated text, without explanations, without comments, without clarifications. "
                        "Only the exact translation:\n\n",
        "bootstyle":    "warning-outline",
        "section":      "Idiomas",
        "shortcut":     "Ctrl+2",
    },
    {
        "label":        "▤  Fix SQL",
        "prompt":       "Actúa como experto en bases de datos. Formatea la consulta, tratando de mantenerla compacta, pero separando bien las secciones de la consulta. Con un Formato Compacto Estructurado y Seccionado. Solo devuelve el código SQL. No lo devuelvas en formato markdown.",
        "bootstyle":    "danger-outline",
        "section":      "Para desarrolladores",
        "shortcut":     "Ctrl+D",
    },
    {
        "label":        "✦  Refactorizar Código",
        "prompt":       "Reescribe el siguiente código para aplicar principios de Clean Code. Mejora el nombrado de variables, reduce la anidación y optimiza la lógica sin alterar su funcionamiento original. Solo devuelve el código. No lo devuelvas en formato markdown.",
        "bootstyle":    "secondary-outline",
        "section":      "Para desarrolladores",
        "shortcut":     "Ctrl+K",
    },
    {
        "label":        "⊙  Explicar Código",
        "prompt":       "Analiza el siguiente código y explica su lógica paso a paso.",
        "bootstyle":    "secondary-outline",
        "section":      "Para desarrolladores",
        "shortcut":     "Ctrl+P",
    },
]
