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
APP_NAME              = "Escriba"
APP_VERSION           = "1.0.5"
GITHUB_REPO           = "cgarciagl/escriba"
UPDATE_CHECK_INTERVAL = 86400  # 24 horas en segundos
STARTUP_KEY           = r"Software\Microsoft\Windows\CurrentVersion\Run"
if sys.platform == "darwin":
    DEFAULT_HOTKEY = "Ctrl+Cmd+E"
    HOTKEY_PRESETS = ["Ctrl+Cmd+E", "Ctrl+Cmd+Space", "Ctrl+Shift+E", "Ctrl+Alt+E"]
    DEFAULT_REPEAT_HOTKEY = ""
    REPEAT_HOTKEY_PRESETS = ["", "Ctrl+Cmd+R", "Ctrl+Shift+R", "Ctrl+Alt+R"]
elif sys.platform == "win32":
    DEFAULT_HOTKEY = "Win+Alt+E"
    HOTKEY_PRESETS = ["Win+Alt+E", "Ctrl+Alt+E", "Ctrl+Shift+E", "Win+Shift+E"]
    DEFAULT_REPEAT_HOTKEY = ""
    REPEAT_HOTKEY_PRESETS = ["", "Ctrl+Alt+R", "Ctrl+Shift+R", "Win+Shift+R"]
else:
    DEFAULT_HOTKEY = "Ctrl+Alt+E"
    HOTKEY_PRESETS = ["Ctrl+Alt+E", "Ctrl+Shift+E", "Super+Alt+E", "Ctrl+Alt+Space"]
    DEFAULT_REPEAT_HOTKEY = ""
    REPEAT_HOTKEY_PRESETS = ["", "Ctrl+Alt+R", "Ctrl+Shift+R", "Super+Alt+R"]

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
HISTORY_FILE       = os.path.join(CONFIG_DIR, "history.json")


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
        "temperature":  0.2,
        "preserve_target_language": True,
    },
    {
        "label":        "◑  Traducir al inglés",
        "prompt":       "Your task is to translate the following text to English. "
                        "Return ONLY the translated text, without explanations, without comments, without clarifications. "
                        "Only the exact translation:\n\n",
        "bootstyle":    "warning-outline",
        "section":      "Idiomas",
        "shortcut":     "Ctrl+2",
        "temperature":  0.2,
        "preserve_target_language": True,
    },
    {
        "label":        "▤  Fix SQL",
        "prompt":       "Actúa como experto en bases de datos. Formatea la consulta, tratando de mantenerla compacta, pero separando bien las secciones de la consulta. Con un Formato Compacto Estructurado y Seccionado. Solo devuelve el código SQL. No lo devuelvas en formato markdown.",
        "bootstyle":    "danger-outline",
        "section":      "Para desarrolladores",
        "shortcut":     "Ctrl+D",
        "temperature":  0.2,
        "strip_markdown": True,
    },
    {
        "label":        "✦  Refactorizar Código",
        "prompt":       "Reescribe el siguiente código para aplicar principios de Clean Code. Mejora el nombrado de variables, reduce la anidación y optimiza la lógica sin alterar su funcionamiento original. Solo devuelve el código. No lo devuelvas en formato markdown.",
        "bootstyle":    "secondary-outline",
        "section":      "Para desarrolladores",
        "shortcut":     "Ctrl+K",
        "temperature":  0.2,
        "strip_markdown": True,
    },
    {
        "label":        "⊙  Explicar Código",
        "prompt":       "Analiza el siguiente código y explica su lógica paso a paso.",
        "bootstyle":    "secondary-outline",
        "section":      "Para desarrolladores",
        "shortcut":     "Ctrl+P",
    },
    {
        "label":        "✉  Redactar correo",
        "prompt":       "Redacta un correo electrónico claro, cordial y profesional sobre: {input:Asunto o idea principal}. "
                        "Devuelve ÚNICAMENTE el texto del correo.",
        "bootstyle":    "info-outline",
        "section":      "Redacción",
        "shortcut":     "Ctrl+3",
        "mode":         "compose",
    },
    {
        "label":        "☑  Lista de tareas",
        "prompt":       "Genera una lista de tareas clara y accionable en formato viñetas sobre: {input:Objetivo o tema}. "
                        "Devuelve ÚNICAMENTE la lista.",
        "bootstyle":    "info-outline",
        "section":      "Redacción",
        "shortcut":     "Ctrl+4",
        "mode":         "compose",
    },
]

AI_ACTIONS_EN = [
    {
        "label":        "✎  Rewrite",
        "prompt":       "Rewrite the following text to improve clarity and flow. "
                        "Return ONLY the rewritten text, without explanations or comments.",
        "bootstyle":    "info-outline",
        "section":      "Text & Content",
        "shortcut":     "Ctrl+R",
    },
    {
        "label":        "◉  Explain",
        "prompt":       "Explain the following text in a detailed yet concise way. "
                        "Be clear and well structured.",
        "bootstyle":    "info-outline",
        "section":      "Text & Content",
        "shortcut":     "Ctrl+E",
    },
    {
        "label":        "⇲  Expand",
        "prompt":       "Expand the following text coherently without hallucinating or inventing information. "
                        "Only elaborate on what is already there without changing the original meaning. "
                        "Return ONLY the expanded text.",
        "bootstyle":    "info-outline",
        "section":      "Text & Content",
        "shortcut":     "Ctrl+L",
    },
    {
        "label":        "≡  Summarize",
        "prompt":       "Generate an executive summary of the following text highlighting the key points.",
        "bootstyle":    "info-outline",
        "section":      "Text & Content",
        "shortcut":     "Ctrl+B",
    },
    {
        "label":        "✉  Improve Email",
        "prompt":       "Improve the following email focusing on clarity, professionalism, and appropriate tone. "
                        "Keep the essential content and original intent. "
                        "Return ONLY the improved email, without explanations or comments.",
        "bootstyle":    "info-outline",
        "section":      "Text & Content",
        "shortcut":     "Ctrl+M",
    },
    {
        "label":        "◐  Translate to Spanish",
        "prompt":       "Your task is to translate the following text to Spanish. "
                        "Return ONLY the translated text, without explanations, without comments, without clarifications. "
                        "Only the exact translation:\n\n",
        "bootstyle":    "warning-outline",
        "section":      "Languages",
        "shortcut":     "Ctrl+1",
        "temperature":  0.2,
        "preserve_target_language": True,
    },
    {
        "label":        "◑  Translate to English",
        "prompt":       "Your task is to translate the following text to English. "
                        "Return ONLY the translated text, without explanations, without comments, without clarifications. "
                        "Only the exact translation:\n\n",
        "bootstyle":    "warning-outline",
        "section":      "Languages",
        "shortcut":     "Ctrl+2",
        "temperature":  0.2,
        "preserve_target_language": True,
    },
    {
        "label":        "▤  Fix SQL",
        "prompt":       "Act as a database expert. Format the query keeping it compact while clearly separating its sections "
                        "with a Structured Compact Sectioned Format. Return ONLY the SQL code. Do not wrap it in markdown.",
        "bootstyle":    "danger-outline",
        "section":      "For Developers",
        "shortcut":     "Ctrl+D",
        "temperature":  0.2,
        "strip_markdown": True,
    },
    {
        "label":        "✦  Refactor Code",
        "prompt":       "Rewrite the following code applying Clean Code principles. Improve variable naming, reduce nesting, "
                        "and optimize logic without changing its original behavior. Return ONLY the code. Do not wrap it in markdown.",
        "bootstyle":    "secondary-outline",
        "section":      "For Developers",
        "shortcut":     "Ctrl+K",
        "temperature":  0.2,
        "strip_markdown": True,
    },
    {
        "label":        "⊙  Explain Code",
        "prompt":       "Analyze the following code and explain its logic step by step.",
        "bootstyle":    "secondary-outline",
        "section":      "For Developers",
        "shortcut":     "Ctrl+P",
    },
    {
        "label":        "✉  Draft Email",
        "prompt":       "Write a clear, polite, and professional email about: {input:Subject or main idea}. "
                        "Return ONLY the email text.",
        "bootstyle":    "info-outline",
        "section":      "Writing",
        "shortcut":     "Ctrl+3",
        "mode":         "compose",
    },
    {
        "label":        "☑  Task List",
        "prompt":       "Generate a clear, actionable bullet-point task list about: {input:Goal or topic}. "
                        "Return ONLY the list.",
        "bootstyle":    "info-outline",
        "section":      "Writing",
        "shortcut":     "Ctrl+4",
        "mode":         "compose",
    },
]


# ─────────────────────────────────────────────────────────────
# Internacionalización (es / en)
# ─────────────────────────────────────────────────────────────
DEFAULT_LANGUAGE = "es"
SUPPORTED_LANGUAGES = ("es", "en")
LANGUAGE_LABELS = {
    "es": "Español",
    "en": "English",
}
AI_LANGUAGE_INSTRUCTIONS = {
    "es": "IMPORTANTE: Responde siempre en español.",
    "en": "IMPORTANT: Always respond in English.",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "es": {
        "app.subtitle": "Asistente de Texto con IA",
        "app.already_running": "{app} ya está ejecutándose en la bandeja del sistema.",
        "wayland.warning": "⚠️ Sesión Wayland detectada.\nInstala {missing} para portapapeles y pegado nativo en Wayland.",
        "wayland.and": " y ",
        "update.available_notify": "🚀 Nueva versión disponible: {app} v{version}\nEstás usando la v{current}.",
        "update.view_notes": "Ver novedades",
        "update.now": "Actualizar ahora",
        "update.view_release": "Ver release",
        "update.downloading": "Descargando {app} v{version}…",
        "update.downloading_pct": "Descargando {app} v{version}… {pct} %",
        "update.error": "❌ No se pudo completar la actualización:\n{error}",
        "update.open_download": "Abrir descarga",
        "update.dialog_title": "{app} — Nueva versión v{version}",
        "update.dialog_header": "🚀 {app} v{version} disponible",
        "update.installed_version": "Versión instalada: v{version}",
        "update.no_notes": "Sin notas de publicación.",
        "update.later": "Más tarde",
        "update.view_github": "🌐 Ver en GitHub",
        "update.install_restart": "⬇  Instalar y reiniciar",
        "hotkey.error": "❌ Error: No se pudo registrar el atajo {hotkey}.\nEs posible que otra aplicación lo esté usando.",
        "hotkey.repeat_fallback": "repetir",
        "tray.no_history": "(sin respuestas todavía)",
        "tray.clear_history": "🗑️  Borrar historial",
        "tray.history": "🕘  Historial",
        "tray.config": "⚙️  Configuración",
        "tray.about": "ℹ️  Acerca de",
        "tray.quit": "❌  Salir",
        "tray.tooltip": "{app} - {hotkey} para activar",
        "common.cancel": "Cancelar",
        "common.cancelling": "Cancelando…",
        "common.close": "Cerrar",
        "common.shortcut_label": "Atajo: ",
        "about.title": "Acerca de {app}",
        "about.version": "Versión {version}",
        "about.desc": "Asistente de texto con IA: selecciona texto en cualquier aplicación y pulsa el atajo para reescribir, traducir, resumir y más.",
        "about.author": "Autor: ",
        "menu.not_configured": "Configura un proveedor de IA antes de usar Escriba.",
        "menu.open_config": "Abrir configuración",
        "menu.placeholder": "Busca una acción o escribe tu propia instrucción",
        "menu.placeholder_compose": "Escribe qué quieres generar o redactar…",
        "menu.word_singular": "palabra",
        "menu.word_plural": "palabras",
        "menu.long_text": "  ·  Texto largo",
        "menu.compose_mode": "  ·  Modo redacción (sin selección)",
        "menu.footer": "↑↓ navegar   ·   Enter ejecutar   ·   Shift+Enter nueva línea   ·   Esc cerrar",
        "menu.warnings": "actions.json tiene avisos:\n{warnings}",
        "menu.section_for_app": "★ Para {app}",
        "menu.section_frequent": "★ Frecuentes",
        "menu.section_recent": "🕘 Instrucciones recientes",
        "menu.verb_use": "Usar como instrucción",
        "menu.verb_generate": "Generar",
        "menu.save_badge": "★ Guardar",
        "menu.saved_ok": "Acción «{label}» guardada en actions.json.",
        "menu.saved_err": "No se pudo guardar la acción: {error}",
        "menu.run": "Ejecutar",
        "menu.free_instruction": "Instrucción libre",
        "result.custom_prompt": "✏️  Prompt personalizado",
        "result.words_range": "{orig} → {res} palabras",
        "result.words_single": "{res} {word}",
        "result.replaced": "Texto sustituido.",
        "result.replace_error": "No se pudo sustituir el texto: {error}",
        "result.cancelled": "Petición cancelada.",
        "result.retry": "Reintentar",
        "result.retrying": "⏳ Modelo ocupado ({attempt}/{max_retries}). Reintentando en {sec} s…",
        "result.generating": "⏳ Generando…",
        "result.tab_result": "Resultado",
        "result.tab_original": "Original",
        "result.tab_diff": "Cambios",
        "result.stop": "⏹  Detener",
        "result.stopping": "Deteniendo…",
        "result.stopped": "⏹ Detenido",
        "result.interrupted": "⚠️ Respuesta interrumpida",
        "result.refine": "✨  Ajustar",
        "result.refining": "✨  Ajustando resultado…",
        "result.refine_prompt": "Refina el texto según las indicaciones del usuario manteniendo fidelidad al original. Devuelve únicamente el resultado.",
        "result.replace_verb": "Sustituir texto",
        "result.insert_verb": "Insertar texto",
        "result.copy": "📋  Copiar",
        "result.copied": "Copiado al portapapeles.",
        "result.regenerate": "🔄  Regenerar",
        "result.regenerating": "🔄  Volviendo a generar…",
        "result.chain": "🔗  Encadenar",
        "result.esc_closes": "Esc cierra",
        "ai.fallback_status": "↪ {primary} falló; probando {secondary}…",
        "ai.no_providers": "No hay proveedores de IA configurados.",
        "actions.default_section": "Texto y Contenido",
        "actions.custom_section": "Personalizadas",
        "config.title": "{app} — Configuración",
        "config.subtitle": "Configuración",
        "config.save_close": "💾  Guardar y Cerrar",
        "config.tab_gemini": "Gemini",
        "config.tab_alt": "Proveedor alternativo",
        "config.tab_actions": "Acciones",
        "config.tab_general": "General",
        "config.welcome": "👋 Te damos la bienvenida a Escriba. Pega tu API Key de Gemini (es gratuita) o configura un proveedor alternativo, y pulsa Guardar.",
        "config.gemini_key": "API Key de Google Gemini",
        "config.gemini_get_key": "Obtén tu clave en → https://aistudio.google.com/apikey",
        "config.key_mac": "Se guarda en el Llavero de macOS.",
        "config.key_win": "Se guarda cifrada con tu cuenta de Windows (DPAPI).",
        "config.gemini_model": "Modelo de Gemini",
        "config.refresh": "🔄 Actualizar",
        "config.gemini_default_hint": "Predeterminado: {model} (rápido y eficiente)",
        "config.alt_hint": "Cualquier servidor compatible con la API de OpenAI: Ollama (local, sin clave), OpenAI, OpenRouter, LM Studio…",
        "config.primary_provider": "Proveedor principal",
        "config.openai_compatible": "Compatible con OpenAI",
        "config.base_url": "URL base",
        "config.api_key_opt": "API Key (opcional)",
        "config.model": "Modelo",
        "config.list": "🔄 Listar",
        "config.fallback_chk": "  Si el proveedor principal falla, usar el otro",
        "config.mode_selection": "Solo selección",
        "config.mode_compose": "Solo redacción",
        "config.mode_both": "Ambos",
        "config.act_label": "Etiqueta (ej. ✎  Reescribir)",
        "config.act_section": "Sección",
        "config.act_shortcut": "Atajo (Ctrl+R)",
        "config.act_mode": "Modo",
        "config.act_temp": "Temp.",
        "config.act_model": "Modelo (opc.)",
        "config.act_apps": "Apps (opc., ej. outlook, code)",
        "config.act_auto": "  Sustituir automáticamente sin abrir ventana",
        "config.act_strip_md": "  Limpiar bloques Markdown (```)",
        "config.act_prompt": "Prompt ({app}, {clipboard}, {lang}, …)",
        "config.act_import": "📥 Importar",
        "config.act_export": "📤 Exportar",
        "config.act_save": "💾  Guardar acciones",
        "config.act_new_label": "✨  Nueva acción",
        "config.act_new_prompt": "Procesa el siguiente texto:",
        "config.act_min_one": "⚠️ Debe quedar al menos una acción.",
        "config.act_import_title": "Importar acciones (JSON)",
        "config.all_files": "Todos",
        "config.act_imported": "📥 {count} acciones importadas (pulsa Guardar para aplicar).",
        "config.act_import_err": "❌ No se pudo importar: {error}",
        "config.act_export_title": "Exportar acciones (JSON)",
        "config.act_exported": "📤 Acciones exportadas a {file}.",
        "config.act_export_err": "❌ No se pudo exportar: {error}",
        "config.act_saved_warn": "⚠️ Acciones guardadas con avisos: {warning}",
        "config.act_saved": "✅ Acciones guardadas en actions.json.",
        "config.act_save_err": "❌ Error al guardar acciones: {error}",
        "config.language": "Idioma / Language:",
        "config.hotkey": "Atajo global:  ",
        "config.repeat_hotkey": "Repetir última:  ",
        "config.streaming": "  Mostrar la respuesta mientras se genera (streaming)",
        "config.rich_paste": "  Pegar con formato enriquecido (Markdown → HTML)",
        "config.persist_history": "  Guardar historial de respuestas entre sesiones",
        "config.autostart": "  Iniciar automáticamente al iniciar sesión",
        "config.auto_update": "  Buscar actualizaciones automáticamente al iniciar",
        "config.current_version": "Versión actual: v{version}",
        "config.check_updates": "🔄  Buscar actualizaciones",
        "config.menu_actions": "Acciones del menú",
        "config.menu_actions_hint": "Puedes editar las acciones en la pestaña 'Acciones' o abrir actions.json directamente. Los cambios se aplican al abrir el menú.",
        "config.open_actions": "📝  Abrir actions.json",
        "config.reset_actions": "↺  Restaurar predeterminadas",
        "config.need_gemini_key": "⚠️ Introduce tu API Key de Gemini para descargar los modelos.",
        "config.fetching_models": "⏳ Consultando modelos disponibles...",
        "config.models_err": "⚠️ No se pudieron consultar los modelos ({error}). Se muestran los predeterminados.",
        "config.models_ok": "✅ Se encontraron {count} modelos de Gemini.",
        "config.need_alt_url": "⚠️ Escribe la URL base del proveedor alternativo.",
        "config.fetching_alt_models": "⏳ Consultando modelos en {base}…",
        "config.alt_models_err": "⚠️ No se pudieron listar modelos. Revisa la URL, la clave o escribe el modelo a mano.",
        "config.alt_models_ok": "✅ Se encontraron {count} modelos.",
        "config.editing_actions": "📝 Editando {path}",
        "config.open_actions_err": "❌ No se pudo abrir actions.json: {error}",
        "config.reset_confirm": "¿Reemplazar actions.json con las acciones predeterminadas?\nSe perderán tus acciones personalizadas.",
        "config.reset_ok": "✅ Acciones restauradas a las predeterminadas.",
        "config.reset_err": "❌ No se pudo restaurar: {error}",
        "config.checking_updates": "⏳ Buscando actualizaciones…",
        "config.updates_err": "⚠️ No se pudo comprobar actualizaciones ({error}).",
        "config.updates_new": "🚀 Nueva versión disponible: v{version}.",
        "config.updates_ok": "✅ Estás al día (v{version}).",
        "config.need_alt_fields": "⚠️ Para usar el proveedor alternativo indica la URL base y el modelo.",
        "config.no_gemini_warn": "\n⚠️ Sin API Key de Gemini no se podrán procesar solicitudes.",
        "config.actions_warn": "\n⚠️ Avisos en acciones: {warning}",
        "config.repeat_conflict": "\n⚠️ El atajo para repetir la última acción no puede coincidir con el atajo principal.",
        "config.autostart_err": "⚠️ No se pudo cambiar el inicio automático: {error}",
        "config.saved_warn": "✅  Configuración guardada.",
        "config.saved_ok": "✅  Configuración guardada correctamente.",
    },
    "en": {
        "app.subtitle": "AI Text Assistant",
        "app.already_running": "{app} is already running in the system tray.",
        "wayland.warning": "⚠️ Wayland session detected.\nInstall {missing} for native clipboard and paste on Wayland.",
        "wayland.and": " and ",
        "update.available_notify": "🚀 New version available: {app} v{version}\nYou are using v{current}.",
        "update.view_notes": "What's new",
        "update.now": "Update now",
        "update.view_release": "View release",
        "update.downloading": "Downloading {app} v{version}…",
        "update.downloading_pct": "Downloading {app} v{version}… {pct}%",
        "update.error": "❌ Could not complete update:\n{error}",
        "update.open_download": "Open download",
        "update.dialog_title": "{app} — New version v{version}",
        "update.dialog_header": "🚀 {app} v{version} available",
        "update.installed_version": "Installed version: v{version}",
        "update.no_notes": "No release notes.",
        "update.later": "Later",
        "update.view_github": "🌐 View on GitHub",
        "update.install_restart": "⬇  Install & restart",
        "hotkey.error": "❌ Error: Could not register shortcut {hotkey}.\nAnother application may already be using it.",
        "hotkey.repeat_fallback": "repeat",
        "tray.no_history": "(no responses yet)",
        "tray.clear_history": "🗑️  Clear history",
        "tray.history": "🕘  History",
        "tray.config": "⚙️  Settings",
        "tray.about": "ℹ️  About",
        "tray.quit": "❌  Quit",
        "tray.tooltip": "{app} - {hotkey} to activate",
        "common.cancel": "Cancel",
        "common.cancelling": "Cancelling…",
        "common.close": "Close",
        "common.shortcut_label": "Shortcut: ",
        "about.title": "About {app}",
        "about.version": "Version {version}",
        "about.desc": "AI text assistant: select text in any application and press the shortcut to rewrite, translate, summarize, and more.",
        "about.author": "Author: ",
        "menu.not_configured": "Configure an AI provider before using Escriba.",
        "menu.open_config": "Open settings",
        "menu.placeholder": "Search an action or type your own instruction",
        "menu.placeholder_compose": "Describe what you want to generate or write…",
        "menu.word_singular": "word",
        "menu.word_plural": "words",
        "menu.long_text": "  ·  Long text",
        "menu.compose_mode": "  ·  Compose mode (no selection)",
        "menu.footer": "↑↓ navigate   ·   Enter run   ·   Shift+Enter new line   ·   Esc close",
        "menu.warnings": "actions.json has warnings:\n{warnings}",
        "menu.section_for_app": "★ For {app}",
        "menu.section_frequent": "★ Frequent",
        "menu.section_recent": "🕘 Recent instructions",
        "menu.verb_use": "Use as instruction",
        "menu.verb_generate": "Generate",
        "menu.save_badge": "★ Save",
        "menu.saved_ok": "Action “{label}” saved to actions.json.",
        "menu.saved_err": "Could not save action: {error}",
        "menu.run": "Run",
        "menu.free_instruction": "Custom instruction",
        "result.custom_prompt": "✏️  Custom prompt",
        "result.words_range": "{orig} → {res} words",
        "result.words_single": "{res} {word}",
        "result.replaced": "Text replaced.",
        "result.replace_error": "Could not replace text: {error}",
        "result.cancelled": "Request cancelled.",
        "result.retry": "Retry",
        "result.retrying": "⏳ Model busy ({attempt}/{max_retries}). Retrying in {sec} s…",
        "result.generating": "⏳ Generating…",
        "result.tab_result": "Result",
        "result.tab_original": "Original",
        "result.tab_diff": "Changes",
        "result.stop": "⏹  Stop",
        "result.stopping": "Stopping…",
        "result.stopped": "⏹ Stopped",
        "result.interrupted": "⚠️ Response interrupted",
        "result.refine": "✨  Refine",
        "result.refining": "✨  Refining result…",
        "result.refine_prompt": "Refine the text according to the user's instructions while staying faithful to the original. Return only the result.",
        "result.replace_verb": "Replace text",
        "result.insert_verb": "Insert text",
        "result.copy": "📋  Copy",
        "result.copied": "Copied to clipboard.",
        "result.regenerate": "🔄  Regenerate",
        "result.regenerating": "🔄  Regenerating…",
        "result.chain": "🔗  Chain",
        "result.esc_closes": "Esc closes",
        "ai.fallback_status": "↪ {primary} failed; trying {secondary}…",
        "ai.no_providers": "No AI providers configured.",
        "actions.default_section": "Text & Content",
        "actions.custom_section": "Custom",
        "config.title": "{app} — Settings",
        "config.subtitle": "Settings",
        "config.save_close": "💾  Save & Close",
        "config.tab_gemini": "Gemini",
        "config.tab_alt": "Alternative provider",
        "config.tab_actions": "Actions",
        "config.tab_general": "General",
        "config.welcome": "👋 Welcome to Escriba. Paste your Gemini API Key (it's free) or configure an alternative provider, then click Save.",
        "config.gemini_key": "Google Gemini API Key",
        "config.gemini_get_key": "Get your key at → https://aistudio.google.com/apikey",
        "config.key_mac": "Stored in the macOS Keychain.",
        "config.key_win": "Stored encrypted with your Windows account (DPAPI).",
        "config.gemini_model": "Gemini model",
        "config.refresh": "🔄 Refresh",
        "config.gemini_default_hint": "Default: {model} (fast and efficient)",
        "config.alt_hint": "Any OpenAI-compatible server: Ollama (local, no key), OpenAI, OpenRouter, LM Studio…",
        "config.primary_provider": "Primary provider",
        "config.openai_compatible": "OpenAI-compatible",
        "config.base_url": "Base URL",
        "config.api_key_opt": "API Key (optional)",
        "config.model": "Model",
        "config.list": "🔄 List",
        "config.fallback_chk": "  If primary provider fails, fall back to the other",
        "config.mode_selection": "Selection only",
        "config.mode_compose": "Compose only",
        "config.mode_both": "Both",
        "config.act_label": "Label (e.g. ✎  Rewrite)",
        "config.act_section": "Section",
        "config.act_shortcut": "Shortcut (Ctrl+R)",
        "config.act_mode": "Mode",
        "config.act_temp": "Temp.",
        "config.act_model": "Model (opt.)",
        "config.act_apps": "Apps (opt., e.g. outlook, code)",
        "config.act_auto": "  Auto-replace without opening result window",
        "config.act_strip_md": "  Strip Markdown code fences (```)",
        "config.act_prompt": "Prompt ({app}, {clipboard}, {lang}, …)",
        "config.act_import": "📥 Import",
        "config.act_export": "📤 Export",
        "config.act_save": "💾  Save actions",
        "config.act_new_label": "✨  New action",
        "config.act_new_prompt": "Process the following text:",
        "config.act_min_one": "⚠️ At least one action must remain.",
        "config.act_import_title": "Import actions (JSON)",
        "config.all_files": "All files",
        "config.act_imported": "📥 {count} actions imported (click Save to apply).",
        "config.act_import_err": "❌ Could not import: {error}",
        "config.act_export_title": "Export actions (JSON)",
        "config.act_exported": "📤 Actions exported to {file}.",
        "config.act_export_err": "❌ Could not export: {error}",
        "config.act_saved_warn": "⚠️ Actions saved with warnings: {warning}",
        "config.act_saved": "✅ Actions saved to actions.json.",
        "config.act_save_err": "❌ Error saving actions: {error}",
        "config.language": "Idioma / Language:",
        "config.hotkey": "Global shortcut:  ",
        "config.repeat_hotkey": "Repeat last:  ",
        "config.streaming": "  Stream response as it is generated",
        "config.rich_paste": "  Paste with rich formatting (Markdown → HTML)",
        "config.persist_history": "  Save response history across sessions",
        "config.autostart": "  Launch automatically at login",
        "config.auto_update": "  Check for updates automatically on startup",
        "config.current_version": "Current version: v{version}",
        "config.check_updates": "🔄  Check for updates",
        "config.menu_actions": "Menu actions",
        "config.menu_actions_hint": "You can edit actions in the 'Actions' tab or open actions.json directly. Changes apply when opening the menu.",
        "config.open_actions": "📝  Open actions.json",
        "config.reset_actions": "↺  Restore defaults",
        "config.need_gemini_key": "⚠️ Enter your Gemini API Key to fetch models.",
        "config.fetching_models": "⏳ Fetching available models...",
        "config.models_err": "⚠️ Could not fetch models ({error}). Showing defaults.",
        "config.models_ok": "✅ Found {count} Gemini models.",
        "config.need_alt_url": "⚠️ Enter the base URL of the alternative provider.",
        "config.fetching_alt_models": "⏳ Fetching models from {base}…",
        "config.alt_models_err": "⚠️ Could not list models. Check URL, key, or type the model manually.",
        "config.alt_models_ok": "✅ Found {count} models.",
        "config.editing_actions": "📝 Editing {path}",
        "config.open_actions_err": "❌ Could not open actions.json: {error}",
        "config.reset_confirm": "Replace actions.json with the default actions?\nYour custom actions will be lost.",
        "config.reset_ok": "✅ Actions restored to defaults.",
        "config.reset_err": "❌ Could not restore: {error}",
        "config.checking_updates": "⏳ Checking for updates…",
        "config.updates_err": "⚠️ Could not check for updates ({error}).",
        "config.updates_new": "🚀 New version available: v{version}.",
        "config.updates_ok": "✅ You are up to date (v{version}).",
        "config.need_alt_fields": "⚠️ To use the alternative provider, enter both the base URL and model.",
        "config.no_gemini_warn": "\n⚠️ Without a Gemini API Key, requests cannot be processed.",
        "config.actions_warn": "\n⚠️ Action warnings: {warning}",
        "config.repeat_conflict": "\n⚠️ The repeat-last shortcut cannot match the main shortcut.",
        "config.autostart_err": "⚠️ Could not change autostart: {error}",
        "config.saved_warn": "✅  Settings saved.",
        "config.saved_ok": "✅  Settings saved successfully.",
    },
}


def translate(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Devuelve la cadena traducida para `key` en `lang` (fallback a español)."""
    table = TRANSLATIONS.get(lang) or TRANSLATIONS[DEFAULT_LANGUAGE]
    text = table.get(key)
    if text is None:
        text = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text

