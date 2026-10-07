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
APP_VERSION  = "1.0.0"
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
STARTUP_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"


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
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


# ─────────────────────────────────────────────────────────────
# Acciones de IA disponibles en el menú flotante
# ─────────────────────────────────────────────────────────────
AI_ACTIONS = [
    {
        "label":        "✎  Reescribir",
        "prompt":       "Reescribe el siguiente texto para mejorar su claridad y fluidez. "
                        "Devuelve ÚNICAMENTE el texto reescrito, sin explicaciones ni comentarios.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+R",
        "shortcut_key": "<Control-r>",
    },
    {
        "label":        "◉  Explicar",
        "prompt":       "Explica de forma detallada pero concisa el siguiente texto. "
                        "Sé claro y estructurado.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+E",
        "shortcut_key": "<Control-e>",
    },
    {
        "label":        "⇲  Extender",
        "prompt":       "Amplía el siguiente texto de forma coherente. Pero sin alucinar ni inventar información. Solo extiende lo que ya está, sin cambiar el sentido original. "
                        "Devuelve ÚNICAMENTE el texto extendido.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+X",
        "shortcut_key": "<Control-x>",
    },
    {
        "label":        "≡  Resumir",
        "prompt":       "Genera un resumen ejecutivo del siguiente texto destacando los puntos clave.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+S",
        "shortcut_key": "<Control-s>",
    },
    {
        "label":        "✉  Mejorar Correo",
        "prompt":       "Mejora el siguiente correo electrónico enfocándote en claridad, profesionalismo y tono adecuado. "
                        "Mantén el contenido esencial y la intención original. "
                        "Devuelve ÚNICAMENTE el correo mejorado, sin explicaciones ni comentarios.",
        "bootstyle":    "info-outline",
        "section":      "Texto y Contenido",
        "shortcut":     "Ctrl+M",
        "shortcut_key": "<Control-m>",
    },
    {
        "label":        "◐  Traducir al español",
        "prompt":       "Tu tarea es traducir el siguiente texto al español. "
                        "Devuelve ÚNICAMENTE el texto traducido, sin explicaciones, sin comentarios, sin aclaraciones. "
                        "Solo la traducción exacta:\n\n",
        "bootstyle":    "warning-outline",
        "section":      "Idiomas",
        "shortcut":     "Ctrl+1",
        "shortcut_key": "<Control-1>",
    },
    {
        "label":        "◑  Traducir al inglés",
        "prompt":       "Your task is to translate the following text to English. "
                        "Return ONLY the translated text, without explanations, without comments, without clarifications. "
                        "Only the exact translation:\n\n",
        "bootstyle":    "warning-outline",
        "section":      "Idiomas",
        "shortcut":     "Ctrl+2",
        "shortcut_key": "<Control-2>",
    },
    {
        "label":        "▤  Fix SQL",
        "prompt":       "Actúa como experto en bases de datos. Formatea la consulta, tratando de mantenerla compacta, pero separando bien las secciones de la consulta. Con un Formato Compacto Estructurado y Seccionado. Solo devuelve el código SQL. No lo devuelvas en formato markdown.",
        "bootstyle":    "danger-outline",
        "section":      "Para desarrolladores",
        "shortcut":     "Ctrl+D",
        "shortcut_key": "<Control-d>",
    },
    {
        "label":        "✦  Refactorizar Código",
        "prompt":       "Reescribe el siguiente código para aplicar principios de Clean Code. Mejora el nombrado de variables, reduce la anidación y optimiza la lógica sin alterar su funcionamiento original. Solo devuelve el código. No lo devuelvas en formato markdown.",
        "bootstyle":    "secondary-outline",
        "section":      "Para desarrolladores",
        "shortcut":     "Ctrl+F",
        "shortcut_key": "<Control-f>",
    },
    {
        "label":        "⊙  Explicar Código",
        "prompt":       "Analiza el siguiente código y explica su lógica paso a paso.",
        "bootstyle":    "secondary-outline",
        "section":      "Para desarrolladores",
        "shortcut":     "Ctrl+P",
        "shortcut_key": "<Control-p>",
    },
]
