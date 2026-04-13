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
# Modelos Gemini en orden de preferencia
# ─────────────────────────────────────────────────────────────
GEMINI_MODELS = [
    "gemini-3.1-flash-lite-preview",   # Más nuevo, bajo costo, baja latencia
    "gemini-3-flash-preview",          # Alto rendimiento, velocidad + inteligencia
    "gemini-2.5-flash",                # Estable, rápido, alto volumen
    "gemini-2.5-flash-lite",           # Estable, ultra-eficiente
]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


# ─────────────────────────────────────────────────────────────
# Acciones de IA disponibles en el menú flotante
# ─────────────────────────────────────────────────────────────
AI_ACTIONS = [
    {
        "label":     "✍️  Reescribir",
        "prompt":    "Reescribe el siguiente texto para mejorar su claridad y fluidez. "
                     "Devuelve ÚNICAMENTE el texto reescrito, sin explicaciones ni comentarios.",
        "bootstyle": "info-outline",
        "section":   "Texto y Contenido",
    },
    {
        "label":     "💡  Explicar",
        "prompt":    "Explica de forma detallada pero concisa el siguiente texto. "
                     "Sé claro y estructurado.",
        "bootstyle": "warning-outline",
        "section":   "Texto y Contenido",
    },
    {
        "label":     "📐  Extender",
        "prompt":    "Amplía el siguiente texto de forma coherente. Pero sin alucinar ni inventar información. Solo extiende lo que ya está, sin cambiar el sentido original."
                     "Devuelve ÚNICAMENTE el texto extendido.",
        "bootstyle": "success-outline",
        "section":   "Texto y Contenido",
    },
    {
        "label":     "📋  Resumir",
        "prompt":    "Genera un resumen ejecutivo del siguiente texto destacando los puntos clave.",
        "bootstyle": "secondary-outline",
        "section":   "Texto y Contenido",
    },
    {
        "label":     "✉️  Mejorar Correo",
        "prompt":    "Mejora el siguiente correo electrónico enfocándote en claridad, profesionalismo y tono adecuado. "
                     "Mantén el contenido esencial y la intención original. "
                     "Devuelve ÚNICAMENTE el correo mejorado, sin explicaciones ni comentarios.",
        "bootstyle": "success-outline",
        "section":   "Texto y Contenido",
    },      
    {
        "label":     "🌐  Traducir al español",
        "prompt":    "Tu tarea es traducir el siguiente texto al español. "
                     "Devuelve ÚNICAMENTE el texto traducido, sin explicaciones, sin comentarios, sin aclaraciones. "
                     "Solo la traducción exacta:\n\n",
        "bootstyle": "warning-outline",
        "section":   "Idiomas",
    },
    {
        "label":     "🗽  Traducir al inglés",
        "prompt":    "Your task is to translate the following text to English. "
                     "Return ONLY the translated text, without explanations, without comments, without clarifications. "
                     "Only the exact translation:\n\n",
        "bootstyle": "warning-outline",
        "section":   "Idiomas",
    },  
    {
        "label":     "🗄️  Fix SQL",
        "prompt":    "Actúa como experto en bases de datos. Formatea la consulta, tratando de mantenerla compacta, pero separando bien las secciones de la consulta. Con un Formato Compacto Estructurado y Seccionado. Solo devuelve el código SQL. No lo devuelvas en formato markdown.",
        "bootstyle": "danger-outline",
        "section":   "Para desarrolladores",
    },
    {
        "label":     "⚙️  Refactorizar Código",
        "prompt":    "Reescribe el siguiente código para aplicar principios de Clean Code. Mejora el nombrado de variables, reduce la anidación y optimiza la lógica sin alterar su funcionamiento original. Solo devuelve el código. No lo devuelvas en formato markdown.",
        "bootstyle": "info-outline",
        "section":   "Para desarrolladores",
    },    
    {
        "label":     "🔍  Explicar Código",
        "prompt":    "Analiza el siguiente código y explica su lógica paso a paso.",
        "bootstyle": "primary-outline",
        "section":   "Para desarrolladores",
    },
]
