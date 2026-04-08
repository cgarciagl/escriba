"""
Escriba - Asistente de Texto con IA para Windows v2.1
======================================================
Hotkey: Ctrl+Shift+Space
- Registrado con RegisterHotKey (API nativa Windows) sobre el HWND
  de la ventana Tk oculta, con polling via root.after().
  Garantiza que la tecla NUNCA filtra a otras aplicaciones.

Stack: ttkbootstrap, pystray, Pillow, pyperclip, ctypes, requests
"""

import os
import sys
import json
import time
import threading
import ctypes
import ctypes.wintypes
import winreg
import tkinter as tk

import ttkbootstrap as tb
from ttkbootstrap.constants import *

import pystray
from PIL import Image, ImageDraw

import pyperclip
import requests
import keyboard


# ─────────────────────────────────────────────────────────────
# Rutas base — funciona tanto en .py como en .exe compilado
# ─────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────
APP_NAME     = "Escriba"
APP_VERSION  = "1.0.0"
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
STARTUP_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"

# Modelos Gemini en orden de preferencia
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash-lite",
]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

AI_ACTIONS = [
    {
        "label":     "✍️  Reescribir",
        "prompt":    "Reescribe el siguiente texto para mejorar su claridad y fluidez. "
                     "Devuelve ÚNICAMENTE el texto reescrito, sin explicaciones ni comentarios.",
        "bootstyle": "info-outline",
    },
    {
        "label":     "💡  Explicar",
        "prompt":    "Explica de forma detallada pero concisa el siguiente texto. "
                     "Sé claro y estructurado.",
        "bootstyle": "warning-outline",
    },
    {
        "label":     "📐  Extender",
        "prompt":    "Amplía el siguiente texto de forma coherente aportando más detalles. "
                     "Devuelve ÚNICAMENTE el texto extendido.",
        "bootstyle": "success-outline",
    },
    {
        "label":     "📋  Resumir",
        "prompt":    "Genera un resumen ejecutivo del siguiente texto destacando los puntos clave.",
        "bootstyle": "secondary-outline",
    },
    {
        "label":     "🌐  Traducir al español",
        "prompt":    "Traduce el siguiente texto al español. "
                     "Devuelve ÚNICAMENTE la traducción, sin explicaciones ni comentarios.",
        "bootstyle": "warning-outline",
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


# ─────────────────────────────────────────────────────────────
# Persistencia (config.json)
# ─────────────────────────────────────────────────────────────
class ConfigManager:

    @staticmethod
    def load() -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # Primer arranque: crear config con autostart activado
        default = {"api_key": "", "autostart": True}
        ConfigManager.save(default)
        StartupManager.enable()
        return default

    @staticmethod
    def save(data: dict):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def get(key: str, default=None):
        return ConfigManager.load().get(key, default)

    @staticmethod
    def set(key: str, value):
        data = ConfigManager.load()
        data[key] = value
        ConfigManager.save(data)

    @staticmethod
    def get_api_key() -> str:
        return ConfigManager.get("api_key", "")

    @staticmethod
    def is_configured() -> bool:
        return bool(ConfigManager.get_api_key().strip())


# ─────────────────────────────────────────────────────────────
# Arranque automático (Registro de Windows)
# ─────────────────────────────────────────────────────────────
class StartupManager:

    @staticmethod
    def _exe_path() -> str:
        """Ruta al ejecutable actual."""
        if getattr(sys, "frozen", False):
            return sys.executable
        # En modo script, apuntar al intérprete + script
        return f'"{sys.executable}" "{os.path.abspath(__file__)}"'

    @staticmethod
    def is_enabled() -> bool:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0,
                                 winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False

    @staticmethod
    def enable():
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0,
                             winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                          StartupManager._exe_path())
        winreg.CloseKey(key)

    @staticmethod
    def disable():
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0,
                                 winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass


# ─────────────────────────────────────────────────────────────
# Hotkey — keyboard library
# ─────────────────────────────────────────────────────────────
class HotkeyManager:
    """
    Usa `keyboard` para registrar Ctrl+Shift+Space globalmente.
    suppress=True evita que la combinación llegue a otras aplicaciones.
    """

    def __init__(self, root: tb.Window, callback):
        self.root     = root
        self.callback = callback
        self._hook    = None

    def start(self):
        def _on_trigger():
            # Liberar modificadores inmediatamente via API nativa antes
            # de ceder el control al hilo, para evitar teclas "pegadas".
            _release_modifiers()
            threading.Thread(target=self.callback, daemon=True).start()

        self._hook = keyboard.add_hotkey(
            'ctrl+shift+space',
            _on_trigger,
            suppress=True,
        )

    def stop(self):
        if self._hook:
            try:
                keyboard.remove_hotkey(self._hook)
            except Exception:
                pass
            self._hook = None


# ─────────────────────────────────────────────────────────────
# Helpers de teclado
# ─────────────────────────────────────────────────────────────
_KEYEVENTF_KEYUP = 0x0002

def _release_modifiers():
    """Suelta Ctrl, Shift y Space via keybd_event (API nativa Windows).
    Más fiable que keyboard.release() porque no pasa por el hook de la librería.
    """
    for vk in (0x11, 0x10, 0x20):  # VK_CONTROL, VK_SHIFT, VK_SPACE
        ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def send_ctrl_c():
    """Suelta los modificadores del hotkey y envía Ctrl+C limpio."""
    _release_modifiers()
    time.sleep(0.08)
    keyboard.send('ctrl+c')


def send_ctrl_v():
    keyboard.send('ctrl+v')


# ─────────────────────────────────────────────────────────────
# Cliente Gemini — auto-detección del modelo disponible
# ─────────────────────────────────────────────────────────────
class GeminiClient:
    _working_model: str = None

    @classmethod
    def generate(cls, prompt: str, text: str) -> str:
        api_key = ConfigManager.get_api_key()
        if not api_key:
            raise ValueError("API Key no configurada.")

        # Intentar el modelo que funcionó antes primero
        candidates = [cls._working_model] + GEMINI_MODELS if cls._working_model else GEMINI_MODELS
        seen, ordered = set(), []
        for m in candidates:
            if m and m not in seen:
                ordered.append(m)
                seen.add(m)

        last_error = "Sin modelos disponibles."
        for model in ordered:
            url = f"{GEMINI_BASE}/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{prompt}\n\n---\n\n{text}"}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
            }
            try:
                r = requests.post(url, json=payload,
                                  headers={"Content-Type": "application/json"},
                                  timeout=60)
                if r.status_code == 404:
                    last_error = f"{model}: no disponible para esta API key (404)"
                    continue
                r.raise_for_status()
                result = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                cls._working_model = model
                return result.strip()
            except requests.HTTPError as e:
                last_error = f"{model}: HTTP {e.response.status_code}"
            except Exception as e:
                last_error = f"{model}: {e}"

        raise RuntimeError(f"Error de API — {last_error}")


# ─────────────────────────────────────────────────────────────
# Cliente gratuito — Pollinations AI (sin API Key)
# ─────────────────────────────────────────────────────────────────────────────
class FreeAIClient:
    _ENDPOINT = "https://text.pollinations.ai/"

    @staticmethod
    def generate(prompt: str, text: str) -> str:
        full_prompt = f"{prompt}\n\n---\n\n{text}"
        payload = {
            "messages": [{"role": "user", "content": full_prompt}],
            "model": "openai",
            "private": True,
        }
        try:
            r = requests.post(
                FreeAIClient._ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            r.raise_for_status()
            result = r.text.strip()
            if not result:
                raise RuntimeError("La respuesta fue vacía.")
            return result
        except Exception as e:
            raise RuntimeError(f"Pollinations AI: {e}")


# ─────────────────────────────────────────────────────────────
# Ventana de Configuración
# ─────────────────────────────────────────────────────────────
class ConfigWindow:
    def __init__(self, app: "EscribaApp"):
        self.app    = app
        self.window = None

    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        win = tb.Toplevel(self.app.root)
        win.title(f"{APP_NAME} — Configuración")
        win.geometry("520x580")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{(sw-520)//2}+{(sh-500)//2}")
        self.window = win

        frame = tb.Frame(win, padding=(30, 24))
        frame.pack(fill=BOTH, expand=True)

        # ── Header ──────────────────────────────────────────
        tb.Label(frame, text=f"⚡ {APP_NAME}",
                 font=("Segoe UI", 22, "bold"), bootstyle="info").pack(pady=(0, 4))
        tb.Label(frame, text="Asistente de Texto con IA",
                 font=("Segoe UI", 10), bootstyle="secondary").pack(pady=(0, 16))
        tb.Separator(frame, bootstyle="info").pack(fill=X, pady=(0, 20))

        # ── API Key ──────────────────────────────────────────
        tb.Label(frame, text="API Key de Google Gemini",
                 font=("Segoe UI", 11, "bold")).pack(anchor=W, pady=(0, 6))

        self.api_key_var = tk.StringVar(value=ConfigManager.get_api_key())
        key_entry = tb.Entry(frame, textvariable=self.api_key_var,
                             show="•", font=("Consolas", 11), bootstyle="info")
        key_entry.pack(fill=X, ipady=6, pady=(0, 6))

        tb.Label(frame, text="Obtén tu clave en → https://aistudio.google.com/apikey",
                 font=("Segoe UI", 9), bootstyle="secondary",
                 cursor="hand2").pack(anchor=W, pady=(0, 20))

        # ── Hotkey Info ──────────────────────────────────────
        tb.Separator(frame, bootstyle="secondary").pack(fill=X, pady=(0, 14))
        hotkey_frame = tb.Frame(frame)
        hotkey_frame.pack(fill=X, pady=(0, 14))
        tb.Label(hotkey_frame, text="Atajo global:",
                 font=("Segoe UI", 10, "bold")).pack(side=LEFT)
        tb.Label(hotkey_frame, text="  Ctrl + Shift + Space",
                 font=("Consolas", 10), bootstyle="info").pack(side=LEFT)

        # ── Arranque con Windows ─────────────────────────────
        tb.Separator(frame, bootstyle="secondary").pack(fill=X, pady=(0, 14))
        self.autostart_var = tk.BooleanVar(value=StartupManager.is_enabled())
        autostart_chk = tb.Checkbutton(
            frame,
            text="  Iniciar automáticamente con Windows",
            variable=self.autostart_var,
            bootstyle="info-round-toggle",
        )
        autostart_chk.pack(anchor=W, pady=(0, 20))

        # ── Status label ─────────────────────────────────────
        self.status_var = tk.StringVar()
        self.status_lbl = tb.Label(frame, textvariable=self.status_var,
                                   font=("Segoe UI", 9), wraplength=460)
        self.status_lbl.pack(anchor=W, pady=(0, 10))

        # ── Botón Guardar ────────────────────────────────────
        tb.Button(frame, text="💾  Guardar y Cerrar",
                  bootstyle="info", width=26,
                  command=self._save).pack()

        key_entry.focus_set()
        win.bind("<Return>", lambda e: self._save())
        win.protocol("WM_DELETE_WINDOW", self._close)

    def _save(self):
        key = self.api_key_var.get().strip()
        # Permitir API Key vacía para configurar solo el autostart
        ConfigManager.set("api_key", key)
        GeminiClient._working_model = None  # forzar re-detección

        # Guardar autostart
        if self.autostart_var.get():
            StartupManager.enable()
        else:
            StartupManager.disable()
        ConfigManager.set("autostart", self.autostart_var.get())

        self.status_var.set("✅  Configuración guardada correctamente.")
        self.status_lbl.configure(bootstyle="success")
        self.window.after(900, self._close)

    def _close(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None


# ─────────────────────────────────────────────────────────────
# Tooltip / Notificación flotante
# ─────────────────────────────────────────────────────────────
class TooltipNotification:
    def __init__(self, root: tb.Window):
        self.root   = root
        self.window = None

    def show(self, message: str, style: str = "info", duration: int = 3500):
        self.hide()
        win = tb.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        self.window = win

        frame = tb.Frame(win, bootstyle=style, padding=(16, 10))
        frame.pack(fill=BOTH, expand=True)
        tb.Label(frame, text=message, font=("Segoe UI", 10),
                 wraplength=370, bootstyle=f"inverse-{style}").pack()

        win.update_idletasks()
        sw  = win.winfo_screenwidth()
        sh  = win.winfo_screenheight()
        w   = win.winfo_reqwidth()
        win.geometry(f"+{sw - w - 22}+{sh - 110}")
        self._fade_in(0.0)
        win.after(duration, lambda: self._fade_out(0.95))

    def _fade_in(self, a):
        if not self.window or not self.window.winfo_exists():
            return
        a = min(a + 0.15, 0.95)
        self.window.attributes("-alpha", a)
        if a < 0.95:
            self.window.after(18, self._fade_in, a)

    def _fade_out(self, a):
        if not self.window or not self.window.winfo_exists():
            return
        a = max(a - 0.10, 0.0)
        self.window.attributes("-alpha", a)
        if a > 0:
            self.window.after(28, self._fade_out, a)
        else:
            self.hide()

    def hide(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None


# ─────────────────────────────────────────────────────────────
# Ventana de "Pensando…" con barra animada
# ─────────────────────────────────────────────────────────────
class ThinkingWindow:
    def __init__(self, root: tb.Window, label: str):
        self.root   = root
        self.window = None
        self._bar   = None
        self.root.after(0, self._show, label)

    def _show(self, label: str):
        win = tb.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        self.window = win

        outer = tb.Frame(win, bootstyle="dark", padding=2)
        outer.pack(fill=BOTH, expand=True)
        inner = tb.Frame(outer, padding=(18, 14))
        inner.pack(fill=BOTH, expand=True)

        tb.Label(inner, text=f"⚡ {APP_NAME}",
                 font=("Segoe UI", 10, "bold"), bootstyle="info").pack(anchor=W)
        tb.Label(inner, text=label,
                 font=("Segoe UI", 10)).pack(anchor=W, pady=(4, 10))

        bar = tb.Progressbar(inner, mode="indeterminate",
                             bootstyle="info-striped", length=240)
        bar.pack(fill=X)
        bar.start(10)
        self._bar = bar

        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w  = win.winfo_reqwidth()
        h  = win.winfo_reqheight()
        win.geometry(f"+{sw - w - 22}+{sh - h - 110}")
        self._fade_in(0.0)

    def _fade_in(self, a):
        if not self.window or not self.window.winfo_exists():
            return
        a = min(a + 0.15, 0.95)
        self.window.attributes("-alpha", a)
        if a < 0.95:
            self.window.after(18, self._fade_in, a)

    def close(self):
        if self.window and self.window.winfo_exists():
            if self._bar:
                try:
                    self._bar.stop()
                except Exception:
                    pass
            self.window.destroy()
        self.window = None


# ─────────────────────────────────────────────────────────────
# Menú Flotante de IA
# ─────────────────────────────────────────────────────────────
class FloatingMenu:
    def __init__(self, app: "EscribaApp"):
        self.app        = app
        self.window     = None
        self._prev_hwnd = None
        self._thinking  = None

    def show(self, selected_text: str):
        self.hide()
        if not selected_text.strip():
            self.app.tooltip.show("⚠️ No se detectó texto seleccionado.\n"
                                  "Selecciona texto y usa Ctrl+Shift+Space.", "warning")
            return

        # Guardar ventana activa para restaurar foco al pegar
        self._prev_hwnd = ctypes.windll.user32.GetForegroundWindow()

        # Posición del cursor sin pyautogui
        point = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        mouse_x, mouse_y = point.x, point.y

        win = tb.Toplevel(self.app.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        self.window = win

        outer = tb.Frame(win, bootstyle="dark", padding=2)
        outer.pack(fill=BOTH, expand=True)
        inner = tb.Frame(outer, padding=(12, 10))
        inner.pack(fill=BOTH, expand=True)

        # ── Header ─────────────────────────────────────────────────────
        hdr = tb.Frame(inner)
        hdr.pack(fill=X, pady=(0, 4))

        tb.Label(hdr, text="⚡", font=("Segoe UI", 13), bootstyle="info").pack(side=LEFT)
        tb.Label(hdr, text=f" {APP_NAME}",
                 font=("Segoe UI", 11, "bold"), bootstyle="info").pack(side=LEFT)

        word_count = len(selected_text.split())
        char_count = len(selected_text.strip())
        tb.Label(hdr, text=f"  {word_count} pal. · {char_count} car.",
                 font=("Segoe UI", 8), bootstyle="secondary").pack(side=LEFT)

        tb.Button(hdr, text="✕", bootstyle="secondary-link",
                  command=self.hide, width=2).pack(side=RIGHT)

        tb.Separator(inner, bootstyle="info").pack(fill=X, pady=(4, 8))

        # ── Preview ────────────────────────────────────────────────────
        preview = selected_text[:80] + ("…" if len(selected_text) > 80 else "")
        prev_frame = tb.Frame(inner, padding=(8, 5))
        prev_frame.pack(fill=X, pady=(0, 10))
        tb.Label(prev_frame, text=f'"{preview}"',
                 font=("Segoe UI", 9, "italic"),
                 bootstyle="secondary", wraplength=305).pack(fill=X)

        # ── Acciones principales — grilla 2 columnas ───────────────────
        main_actions = [a for a in AI_ACTIONS if not a.get("section")]
        grid = tb.Frame(inner)
        grid.pack(fill=X, pady=(0, 4))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        for i, action in enumerate(main_actions):
            row, col = divmod(i, 2)
            span = 2 if (i == len(main_actions) - 1 and len(main_actions) % 2 != 0) else 1
            btn = tb.Button(grid, text=action["label"],
                            bootstyle=action["bootstyle"],
                            command=lambda a=action: self._on_action(a, selected_text))
            btn.grid(row=row, column=col, columnspan=span, sticky="ew",
                     padx=(0, 2) if col == 0 else (2, 0), pady=2, ipady=5)

        # ── Sección Desarrolladores ────────────────────────────────────
        dev_actions = [a for a in AI_ACTIONS if a.get("section")]
        if dev_actions:
            sections: dict = {}
            for a in dev_actions:
                sec = a.get("section", "")
                sections.setdefault(sec, []).append(a)

            for sec_name, sec_actions in sections.items():
                tb.Separator(inner, bootstyle="secondary").pack(fill=X, pady=(8, 5))
                sec_hdr = tb.Frame(inner)
                sec_hdr.pack(fill=X, pady=(0, 4))
                tb.Label(sec_hdr, text="</>",
                         font=("Consolas", 8, "bold"), bootstyle="secondary").pack(side=LEFT)
                tb.Label(sec_hdr, text=f"  {sec_name.upper()}",
                         font=("Segoe UI", 8, "bold"), bootstyle="secondary").pack(side=LEFT)

                dev_grid = tb.Frame(inner)
                dev_grid.pack(fill=X)
                dev_grid.columnconfigure(0, weight=1)
                dev_grid.columnconfigure(1, weight=1)

                for i, action in enumerate(sec_actions):
                    row, col = divmod(i, 2)
                    span = 2 if (i == len(sec_actions) - 1 and len(sec_actions) % 2 != 0) else 1
                    btn = tb.Button(dev_grid, text=action["label"],
                                    bootstyle=action["bootstyle"],
                                    command=lambda a=action: self._on_action(a, selected_text))
                    btn.grid(row=row, column=col, columnspan=span, sticky="ew",
                             padx=(0, 2) if col == 0 else (2, 0), pady=2, ipady=4)

        # ── Prompt personalizado ───────────────────────────────────────
        tb.Separator(inner, bootstyle="secondary").pack(fill=X, pady=(8, 5))
        tb.Button(inner, text="✏️  Crear prompt personalizado",
                  bootstyle="primary",
                  command=lambda: self._on_custom_prompt(selected_text)
                  ).pack(fill=X, pady=(0, 2), ipady=6)

        win.update_idletasks()
        w, h   = win.winfo_reqwidth(), win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = mouse_x + 14 if mouse_x + 14 + w < sw else mouse_x - w - 14
        y = mouse_y + 14 if mouse_y + 14 + h < sh else mouse_y - h - 14
        win.geometry(f"+{x}+{y}")

        self._fade_in(0.0)
        win.bind("<Escape>", lambda e: self.hide())
        win.bind("<FocusOut>", lambda e: win.after(220, self._check_focus))
        win.focus_force()

    def _fade_in(self, a):
        if not self.window or not self.window.winfo_exists():
            return
        a = min(a + 0.15, 0.97)
        self.window.attributes("-alpha", a)
        if a < 0.97:
            self.window.after(18, self._fade_in, a)

    def _check_focus(self):
        if not self.window or not self.window.winfo_exists():
            return
        try:
            f = self.window.focus_get()
            if f is None or not str(f).startswith(str(self.window)):
                self.hide()
        except Exception:
            self.hide()

    def hide(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None

    def _on_action(self, action: dict, text: str):
        self.hide()
        self._thinking = ThinkingWindow(self.app.root, f"{action['label'].strip()}…")
        threading.Thread(target=self._process, args=(action, text), daemon=True).start()

    def _on_custom_prompt(self, selected_text: str):
        self.hide()
        CustomPromptWindow(self.app, selected_text, self._prev_hwnd)

    def _process(self, action: dict, text: str):
        def close_thinking():
            if self._thinking:
                self._thinking.close()
                self._thinking = None
        try:
            result = None
            last_error = None
            used_gemini = False
            if ConfigManager.is_configured():
                try:
                    result = GeminiClient.generate(action["prompt"], text)
                    used_gemini = True
                except Exception as e:
                    last_error = str(e)
            if result is None:
                try:
                    result = FreeAIClient.generate(action["prompt"], text)
                except Exception as e:
                    if last_error:
                        raise RuntimeError(f"Gemini: {last_error} | Pollinations: {e}")
                    raise
            self.app.root.after(0, close_thinking)
            self.app.root.after(0, lambda: ResultWindow(
                self.app, result, self._prev_hwnd,
                prompt=action["prompt"], selected_text=text,
                used_gemini=used_gemini))
        except Exception as e:
            self.app.root.after(0, close_thinking)
            self.app.root.after(0, self.app.tooltip.show,
                                f"❌ {str(e)[:180]}", "danger", 6000)


# ─────────────────────────────────────────────────────────────
# Ventana de Prompt Personalizado
# ─────────────────────────────────────────────────────────────
class CustomPromptWindow:
    def __init__(self, app: "EscribaApp", selected_text: str, prev_hwnd):
        self.app           = app
        self.selected_text = selected_text
        self.prev_hwnd     = prev_hwnd

        win = tb.Toplevel(app.root)
        win.title(f"{APP_NAME} — Prompt personalizado")
        win.attributes("-topmost", True)
        win.resizable(True, True)
        self.window = win

        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = 520, 340
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        frame = tb.Frame(win, padding=(16, 12))
        frame.pack(fill=BOTH, expand=True)

        tb.Label(frame, text="✏️  Escribe tu prompt",
                 font=("Segoe UI", 12, "bold"), bootstyle="info").pack(anchor=W, pady=(0, 4))

        preview = selected_text[:75] + ("…" if len(selected_text) > 75 else "")
        tb.Label(frame, text=f'Texto seleccionado: "{preview}"',
                 font=("Segoe UI", 9, "italic"),
                 bootstyle="secondary", wraplength=480).pack(anchor=W, pady=(0, 8))

        tb.Separator(frame, bootstyle="info").pack(fill=X, pady=(0, 8))

        btn_frame = tb.Frame(frame)
        btn_frame.pack(side=BOTTOM, fill=X, pady=(8, 0))
        tb.Button(btn_frame, text="🚀  Ejecutar",
                  bootstyle="info",
                  command=self._execute).pack(side=LEFT, expand=True, fill=X, padx=(0, 6), ipady=4)
        tb.Button(btn_frame, text="✕  Cancelar",
                  bootstyle="danger-outline",
                  command=win.destroy).pack(side=LEFT, expand=True, fill=X, ipady=4)

        txt_frame = tb.Frame(frame)
        txt_frame.pack(fill=BOTH, expand=True)

        scrollbar = tb.Scrollbar(txt_frame, bootstyle="info-round")
        scrollbar.pack(side=RIGHT, fill=Y)

        self.prompt_widget = tk.Text(
            txt_frame,
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            relief="flat",
            padx=8, pady=8,
            yscrollcommand=scrollbar.set,
        )
        self.prompt_widget.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.prompt_widget.yview)
        self.prompt_widget.focus_set()

        win.bind("<Control-Return>", lambda e: self._execute())

    def _execute(self):
        custom_prompt = self.prompt_widget.get("1.0", tk.END).strip()
        if not custom_prompt:
            self.app.tooltip.show("⚠️ El prompt no puede estar vacío.", "warning")
            return
        self.window.destroy()
        action = {"label": "✏️  Prompt personalizado", "prompt": custom_prompt}
        thinking = ThinkingWindow(self.app.root, "✏️  Prompt personalizado…")
        threading.Thread(
            target=self._process, args=(action, thinking), daemon=True
        ).start()

    def _process(self, action: dict, thinking: ThinkingWindow):
        def close_thinking():
            thinking.close()
        try:
            result = None
            last_error = None
            used_gemini = False
            if ConfigManager.is_configured():
                try:
                    result = GeminiClient.generate(action["prompt"], self.selected_text)
                    used_gemini = True
                except Exception as e:
                    last_error = str(e)
            if result is None:
                try:
                    result = FreeAIClient.generate(action["prompt"], self.selected_text)
                except Exception as e:
                    if last_error:
                        raise RuntimeError(f"Gemini: {last_error} | Pollinations: {e}")
                    raise
            self.app.root.after(0, close_thinking)
            self.app.root.after(0, lambda: ResultWindow(
                self.app, result, self.prev_hwnd,
                prompt=action["prompt"], selected_text=self.selected_text,
                used_gemini=used_gemini))
        except Exception as e:
            self.app.root.after(0, close_thinking)
            self.app.root.after(0, self.app.tooltip.show,
                                f"❌ {str(e)[:180]}", "danger", 6000)


# ─────────────────────────────────────────────────────────────
# Ventana de Resultado con botón Sustituir
# ─────────────────────────────────────────────────────────────
class ResultWindow:
    _last_pollinations_ts: float = 0.0   # timestamp de la última llamada a Pollinations
    _POLLINATIONS_COOLDOWN = 10          # segundos de espera entre regeneraciones

    def __init__(self, app: "EscribaApp", result: str, prev_hwnd,
                 prompt: str = "", selected_text: str = "",
                 used_gemini: bool = False):
        self.app           = app
        self.result        = result
        self.prev_hwnd     = prev_hwnd
        self.prompt        = prompt
        self.selected_text = selected_text
        self.used_gemini   = used_gemini

        if not used_gemini:
            ResultWindow._last_pollinations_ts = time.time()

        win = tb.Toplevel(app.root)
        win.title(f"{APP_NAME} — Resultado")
        win.attributes("-topmost", True)
        win.resizable(True, True)
        self.window = win

        # Centrar en pantalla
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = 580, 420
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        frame = tb.Frame(win, padding=(16, 12))
        frame.pack(fill=BOTH, expand=True)

        # Header
        hdr = tb.Frame(frame)
        hdr.pack(fill=X, pady=(0, 8))
        tb.Label(hdr, text="✨ Texto generado",
                 font=("Segoe UI", 12, "bold"), bootstyle="info").pack(side=LEFT)

        tb.Separator(frame, bootstyle="info").pack(fill=X, pady=(0, 10))

        # Botones — se empaquetan primero con side=BOTTOM para garantizar visibilidad
        btn_bot = tb.Frame(frame)
        btn_bot.pack(side=BOTTOM, fill=X, pady=(6, 0))

        tb.Button(btn_bot, text="📋  Copiar al portapapeles",
                  bootstyle="secondary-outline",
                  command=self._copy).pack(side=LEFT, expand=True, fill=X, padx=(0, 6), ipady=4)

        tb.Button(btn_bot, text="✕  Cerrar",
                  bootstyle="danger-outline",
                  command=win.destroy).pack(side=LEFT, expand=True, fill=X, ipady=4)

        btn_mid = tb.Frame(frame)
        btn_mid.pack(side=BOTTOM, fill=X, pady=(0, 6))

        has_prompt = bool(self.prompt)
        self._regen_btn = tb.Button(
            btn_mid, text="🔄  Volver a generar",
            bootstyle="warning" if has_prompt else "secondary",
            command=self._regenerate if has_prompt else lambda: None,
            state="normal" if has_prompt else "disabled",
        )
        self._regen_btn.pack(side=LEFT, expand=True, fill=X, padx=(0, 6), ipady=4)

        # Iniciar cooldown visual si la respuesta vino de Pollinations
        if has_prompt and not used_gemini:
            self._start_cooldown()

        tb.Button(btn_mid, text="⬅️  Sustituir texto seleccionado",
                  bootstyle="info",
                  command=self._replace).pack(side=LEFT, expand=True, fill=X, ipady=4)

        # Área de texto editable — ocupa el espacio restante
        txt_frame = tb.Frame(frame)
        txt_frame.pack(fill=BOTH, expand=True, pady=(0, 6))

        scrollbar = tb.Scrollbar(txt_frame, bootstyle="info-round")
        scrollbar.pack(side=RIGHT, fill=Y)

        self.text_widget = tk.Text(
            txt_frame,
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            relief="flat",
            padx=8, pady=8,
            yscrollcommand=scrollbar.set,
        )
        self.text_widget.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.text_widget.yview)
        self.text_widget.insert("1.0", result)
        self.text_widget.focus_set()

        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def _copy(self):
        text = self.text_widget.get("1.0", tk.END).strip()
        pyperclip.copy(text)
        self.app.tooltip.show("📋 Copiado al portapapeles.", "info", 2000)

    def _replace(self):
        text = self.text_widget.get("1.0", tk.END).strip()
        self.window.destroy()
        # Ejecutar en hilo separado para poder manejar el foco sin bloquear Tk
        threading.Thread(target=self._do_replace, args=(text,), daemon=True).start()

    def _do_replace(self, text: str):
        try:
            pyperclip.copy(text)
            if self.prev_hwnd:
                fore_tid = ctypes.windll.user32.GetWindowThreadProcessId(
                    self.prev_hwnd, None)
                cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
                if fore_tid and fore_tid != cur_tid:
                    ctypes.windll.user32.AttachThreadInput(cur_tid, fore_tid, True)
                ctypes.windll.user32.SetForegroundWindow(self.prev_hwnd)
                ctypes.windll.user32.BringWindowToTop(self.prev_hwnd)
                if fore_tid and fore_tid != cur_tid:
                    ctypes.windll.user32.AttachThreadInput(cur_tid, fore_tid, False)
                time.sleep(0.25)
            send_ctrl_v()
            self.app.root.after(
                0, lambda: self.app.tooltip.show("✅ Texto sustituido.", "success"))
        except Exception as e:
            self.app.root.after(
                0, lambda: self.app.tooltip.show(f"❌ Error al sustituir: {e}", "danger"))

    def _start_cooldown(self):
        """Deshabilita el botón regenerar y muestra cuenta regresiva."""
        elapsed = time.time() - ResultWindow._last_pollinations_ts
        remaining = self._POLLINATIONS_COOLDOWN - elapsed
        if remaining <= 0:
            return
        self._regen_btn.configure(state="disabled")
        self._tick_cooldown(remaining)

    def _tick_cooldown(self, remaining: float):
        if not self.window or not self.window.winfo_exists():
            return
        if remaining <= 0:
            self._regen_btn.configure(
                text="🔄  Volver a generar", state="normal", bootstyle="warning")
            return
        secs = int(remaining) + 1
        self._regen_btn.configure(
            text=f"🔄  Espera {secs}s…", bootstyle="secondary")
        self.window.after(500, self._tick_cooldown, remaining - 0.5)

    def _regenerate(self):
        self.window.destroy()
        thinking = ThinkingWindow(self.app.root, "🔄  Volver a generar…")
        threading.Thread(
            target=self._do_regenerate, args=(thinking,), daemon=True
        ).start()

    def _do_regenerate(self, thinking: ThinkingWindow):
        def close_thinking():
            thinking.close()
        try:
            result = None
            last_error = None
            used_gemini = False
            # Forzar re-detección de modelo para evitar quedarnos en uno con error
            GeminiClient._working_model = None
            if ConfigManager.is_configured():
                try:
                    result = GeminiClient.generate(self.prompt, self.selected_text)
                    used_gemini = True
                except Exception as e:
                    last_error = str(e)
            if result is None:
                try:
                    result = FreeAIClient.generate(self.prompt, self.selected_text)
                except Exception as e:
                    if last_error:
                        raise RuntimeError(f"Gemini: {last_error} | Pollinations: {e}")
                    raise
            self.app.root.after(0, close_thinking)
            self.app.root.after(0, lambda: ResultWindow(
                self.app, result, self.prev_hwnd,
                prompt=self.prompt, selected_text=self.selected_text,
                used_gemini=used_gemini))
        except Exception as e:
            self.app.root.after(0, close_thinking)
            self.app.root.after(0, self.app.tooltip.show,
                                f"❌ {str(e)[:180]}", "danger", 6000)


# ─────────────────────────────────────────────────────────────
# System Tray
# ─────────────────────────────────────────────────────────────
class TrayIconManager:
    def __init__(self, app: "EscribaApp"):
        self.app  = app
        self.icon = None

    @staticmethod
    def _build_image() -> Image.Image:
        ico_path = os.path.join(BASE_DIR, "escriba.ico")
        if os.path.exists(ico_path):
            try:
                img = Image.open(ico_path)
                img = img.convert("RGBA").resize((64, 64), Image.LANCZOS)
                return img
            except Exception:
                pass
        # Fallback generado
        size = 64
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([4, 4, 60, 60], radius=14,
                               fill=(18, 16, 32, 255),
                               outline=(0, 210, 180, 255), width=3)
        draw.ellipse([20, 20, 44, 44], fill=(0, 210, 180, 200))
        return img

    def start(self):
        image = self._build_image()
        menu  = pystray.Menu(
            pystray.MenuItem(f"{APP_NAME} v{APP_VERSION}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️  Configuración",
                             lambda icon, item: self.app.root.after(0, self.app.open_config)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌  Salir",
                             lambda icon, item: self.app.root.after(0, self.app.quit_app)),
        )
        self.icon = pystray.Icon(
            APP_NAME, image,
            f"{APP_NAME} — Ctrl+Shift+Space para activar",
            menu,
        )
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────
# Banner de bienvenida
# ─────────────────────────────────────────────────────────────
class SplashBanner:
    """Pequeño banner esquina inferior-derecha que aparece al iniciar y se
    desvanece solo tras `duration` ms.
    """
    _SHOW_MS  = 3800
    _HOLD_MS  = 2800

    def __init__(self, root: tb.Window):
        self.root   = root
        self.window = None
        self.root.after(300, self._show)

    def _show(self):
        win = tb.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        self.window = win

        # Contenedor con borde sutil
        outer = tb.Frame(win, bootstyle="info", padding=2)
        outer.pack(fill=BOTH, expand=True)
        inner = tb.Frame(outer, padding=(18, 14, 18, 14))
        inner.pack(fill=BOTH, expand=True)

        # Icono + nombre
        hdr = tb.Frame(inner)
        hdr.pack(fill=X)
        tb.Label(hdr, text="⚡",
                 font=("Segoe UI", 22), bootstyle="info").pack(side=LEFT, padx=(0, 8))
        title_frame = tb.Frame(hdr)
        title_frame.pack(side=LEFT)
        tb.Label(title_frame, text=APP_NAME,
                 font=("Segoe UI", 16, "bold"), bootstyle="info").pack(anchor=W)
        tb.Label(title_frame, text="Asistente de Texto con IA",
                 font=("Segoe UI", 9), bootstyle="secondary").pack(anchor=W)

        tb.Separator(inner, bootstyle="info").pack(fill=X, pady=(10, 8))

        # Pista del atajo
        hint = tb.Frame(inner)
        hint.pack(fill=X)
        tb.Label(hint, text="Atajo: ",
                 font=("Segoe UI", 9), bootstyle="secondary").pack(side=LEFT)
        tb.Label(hint, text="Ctrl + Shift + Space",
                 font=("Consolas", 9, "bold"), bootstyle="info").pack(side=LEFT)

        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w  = win.winfo_reqwidth()
        h  = win.winfo_reqheight()
        win.geometry(f"+{sw - w - 22}+{sh - h - 110}")

        self._fade_in(0.0)
        win.after(self._HOLD_MS, lambda: self._fade_out(0.95))

    def _fade_in(self, a):
        if not self.window or not self.window.winfo_exists():
            return
        a = min(a + 0.12, 0.95)
        self.window.attributes("-alpha", a)
        if a < 0.95:
            self.window.after(18, self._fade_in, a)

    def _fade_out(self, a):
        if not self.window or not self.window.winfo_exists():
            return
        a = max(a - 0.07, 0.0)
        self.window.attributes("-alpha", a)
        if a > 0:
            self.window.after(28, self._fade_out, a)
        else:
            if self.window and self.window.winfo_exists():
                self.window.destroy()
            self.window = None


# ─────────────────────────────────────────────────────────────
# Aplicación Principal
# ─────────────────────────────────────────────────────────────
class EscribaApp:
    def __init__(self):
        self.root    = tb.Window(themename="vapor")
        self.root.title(APP_NAME)
        self.root.withdraw()

        self.config_window = ConfigWindow(self)
        self.floating_menu = FloatingMenu(self)
        self.tooltip       = TooltipNotification(self.root)
        self.tray          = TrayIconManager(self)
        self.hotkey        = HotkeyManager(self.root, self._on_hotkey)
        self._lock         = threading.Lock()

    def run(self):
        # Garantiza que config.json existe desde el primer arranque
        ConfigManager.load()
        self.tray.start()
        SplashBanner(self.root)
        # El hotkey se registra DESPUÉS de que Tk haya creado la ventana
        self.root.after(500, self.hotkey.start)
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.mainloop()

    def open_config(self):
        self.config_window.show()

    def quit_app(self):
        self.hotkey.stop()
        self.tray.stop()
        self.floating_menu.hide()
        self.tooltip.hide()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def _on_hotkey(self):
        """Ejecutado en hilo secundario al detectar Ctrl+Shift+Space."""
        if not self._lock.acquire(blocking=False):
            return
        try:
            # Guardar portapapeles actual
            old_clip = ""
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass

            # Copiar selección (send_ctrl_c suelta modificadores antes)
            send_ctrl_c()
            time.sleep(0.40)

            try:
                selected = pyperclip.paste()
            except Exception:
                selected = ""

            # Si no cambió, intentar de nuevo
            if selected == old_clip:
                send_ctrl_c()
                time.sleep(0.35)
                try:
                    selected = pyperclip.paste()
                except Exception:
                    selected = ""

            self.root.after(0, self.floating_menu.show, selected)
        finally:
            self._lock.release()


# ─────────────────────────────────────────────────────────────
# Punto de entrada
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = EscribaApp()
    app.run()
