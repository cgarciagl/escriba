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
        "label":     "🗄️  Fix SQL",
        "prompt":    "Actúa como experto en bases de datos. Formatea la siguiente consulta SQL "
                     "con un Formato Compacto Estructurado y Seccionado. Solo devuelve el código SQL.",
        "bootstyle": "danger-outline",
    },
    {
        "label":     "🔍  Explicar Código",
        "prompt":    "Analiza el siguiente código y explica su lógica paso a paso.",
        "bootstyle": "primary-outline",
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
        self._hook = keyboard.add_hotkey(
            'ctrl+shift+space',
            lambda: threading.Thread(target=self.callback, daemon=True).start(),
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
def send_ctrl_c():
    """Suelta los modificadores del hotkey y envía Ctrl+C limpio."""
    keyboard.release('ctrl')
    keyboard.release('shift')
    keyboard.release('space')
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
        if not key:
            self.status_var.set("⚠️  La API Key no puede estar vacía.")
            self.status_lbl.configure(bootstyle="warning")
            return

        # Guardar API Key
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
        inner = tb.Frame(outer, padding=10)
        inner.pack(fill=BOTH, expand=True)

        # Header
        hdr = tb.Frame(inner)
        hdr.pack(fill=X, pady=(0, 6))
        tb.Label(hdr, text=f"⚡ {APP_NAME}",
                 font=("Segoe UI", 11, "bold"), bootstyle="info").pack(side=LEFT)
        tb.Button(hdr, text="✕", bootstyle="secondary-link",
                  command=self.hide, width=3).pack(side=RIGHT)

        tb.Separator(inner, bootstyle="info").pack(fill=X, pady=(0, 8))

        preview = selected_text[:75] + ("…" if len(selected_text) > 75 else "")
        tb.Label(inner, text=f'"{preview}"',
                 font=("Segoe UI", 9, "italic"),
                 bootstyle="secondary", wraplength=285).pack(fill=X, pady=(0, 8))

        for action in AI_ACTIONS:
            tb.Button(inner, text=action["label"],
                      bootstyle=action["bootstyle"], width=28,
                      command=lambda a=action: self._on_action(a, selected_text)
                      ).pack(fill=X, pady=2, ipady=4)

        win.update_idletasks()
        w, h   = win.winfo_reqwidth(), win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = mouse_x + 14 if mouse_x + 14 + w < sw else mouse_x - w - 14
        y = mouse_y + 14 if mouse_y + 14 + h < sh else mouse_y - h - 14
        win.geometry(f"+{x}+{y}")

        self._fade_in(0.0)
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

    def _process(self, action: dict, text: str):
        def close_thinking():
            if self._thinking:
                self._thinking.close()
                self._thinking = None
        try:
            result = None
            last_error = None
            if ConfigManager.is_configured():
                try:
                    result = GeminiClient.generate(action["prompt"], text)
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
            self.app.root.after(0, lambda: ResultWindow(self.app, result, self._prev_hwnd))
        except Exception as e:
            self.app.root.after(0, close_thinking)
            self.app.root.after(0, self.app.tooltip.show,
                                f"❌ {str(e)[:180]}", "danger", 6000)


# ─────────────────────────────────────────────────────────────
# Ventana de Resultado con botón Sustituir
# ─────────────────────────────────────────────────────────────
class ResultWindow:
    def __init__(self, app: "EscribaApp", result: str, prev_hwnd):
        self.app       = app
        self.result    = result
        self.prev_hwnd = prev_hwnd

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

        btn_top = tb.Frame(frame)
        btn_top.pack(side=BOTTOM, fill=X, pady=(0, 6))

        tb.Button(btn_top, text="⬅️  Sustituir texto seleccionado",
                  bootstyle="info",
                  command=self._replace).pack(fill=X, ipady=6)

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
