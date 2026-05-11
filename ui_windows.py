"""
Escriba — Ventanas de la interfaz gráfica.

Contiene: TooltipNotification, ThinkingWindow, SplashBanner,
          ConfigWindow, FloatingMenu, CustomPromptWindow, ResultWindow.
"""

from __future__ import annotations

import time
import threading
import ctypes
import ctypes.wintypes
import tkinter as tk
from typing import TYPE_CHECKING

import ttkbootstrap as tb
from ttkbootstrap.constants import *

import pyperclip

import webbrowser
from constants import APP_NAME, AI_ACTIONS
from config import ConfigManager
from startup import StartupManager
from ai_clients import GeminiClient, generate_with_fallback
from hotkey import send_ctrl_v

if TYPE_CHECKING:
    from escriba import EscribaApp


# ─────────────────────────────────────────────────────────────
# Helpers de UI
# ─────────────────────────────────────────────────────────────
def fade_window(window, target: float, step: float, interval: int = 18, on_done=None):
    """Anima alpha de una ventana hacia target."""
    if not window or not window.winfo_exists():
        return
    try:
        current = float(window.attributes("-alpha"))
        if step > 0:
            new_alpha = min(current + step, target)
        else:
            new_alpha = max(current + step, target)
        window.attributes("-alpha", new_alpha)
        if (step > 0 and new_alpha < target) or (step < 0 and new_alpha > target):
            window.after(interval, fade_window, window, target, step, interval, on_done)
        elif on_done:
            on_done()
    except Exception:
        pass


def run_ai_action(app, prompt, text, prev_hwnd, thinking):
    """Ejecuta una acción de IA en hilo secundario — reutilizable."""
    def close():
        thinking.close()
    try:
        result, used_gemini = generate_with_fallback(prompt, text)
        app.root.after(0, close)
        app.root.after(0, lambda: ResultWindow(
            app, result, prev_hwnd,
            prompt=prompt, selected_text=text,
            used_gemini=used_gemini))
    except Exception as e:
        app.root.after(0, close)
        app.root.after(0, app.tooltip.show,
                       f"❌ {str(e)[:180]}", "danger", 6000)


# ─────────────────────────────────────────────────────────────
# Tooltip / Notificación flotante
# ─────────────────────────────────────────────────────────────
class TooltipNotification:
    """Muestra una notificación flotante con fade-in/out."""

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
        fade_window(win, 0.95, 0.15)
        win.after(duration, lambda: fade_window(win, 0.0, -0.10, on_done=self.hide))


    def hide(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None


# ─────────────────────────────────────────────────────────────
# Ventana de "Pensando…" con barra animada
# ─────────────────────────────────────────────────────────────
class ThinkingWindow:
    """Indicador de progreso indeterminado mientras la IA trabaja."""

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
        fade_window(win, 0.95, 0.15)


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
# Banner de bienvenida
# ─────────────────────────────────────────────────────────────
class SplashBanner:
    """Pequeño banner esquina inferior-derecha que aparece al iniciar y se
    desvanece solo tras un tiempo.
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
        tb.Label(hint, text="Win + Alt + E",
                 font=("Consolas", 9, "bold"), bootstyle="info").pack(side=LEFT)

        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        w  = win.winfo_reqwidth()
        h  = win.winfo_reqheight()
        win.geometry(f"+{sw - w - 22}+{sh - h - 110}")

        fade_window(win, 0.95, 0.12)
        win.after(self._HOLD_MS, lambda: fade_window(win, 0.0, -0.07, on_done=lambda: win.destroy() if win.winfo_exists() else None))



# ─────────────────────────────────────────────────────────────
# Ventana de Configuración
# ─────────────────────────────────────────────────────────────
class ConfigWindow:
    """Formulario para API Key, autostart y configuración general."""

    def __init__(self, app: EscribaApp):
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

        url_label = tb.Label(frame, text="Obtén tu clave en → https://aistudio.google.com/apikey",
                 font=("Segoe UI", 9), bootstyle="secondary",
                 cursor="hand2")
        url_label.pack(anchor=W, pady=(0, 20))
        url_label.bind("<Button-1>", lambda e: webbrowser.open("https://aistudio.google.com/apikey"))

        # ── Hotkey Info ──────────────────────────────────────
        tb.Separator(frame, bootstyle="secondary").pack(fill=X, pady=(0, 14))
        hotkey_frame = tb.Frame(frame)
        hotkey_frame.pack(fill=X, pady=(0, 14))
        tb.Label(hotkey_frame, text="Atajo global:",
                 font=("Segoe UI", 10, "bold")).pack(side=LEFT)
        tb.Label(hotkey_frame, text="  Win + Alt + E",
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
        ConfigManager.set("api_key", key)
        GeminiClient._working_model = None  # forzar re-detección

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
# Menú Flotante de IA
# ─────────────────────────────────────────────────────────────
class FloatingMenu:
    """Menú contextual con las acciones de IA sobre el texto seleccionado."""

    def __init__(self, app: EscribaApp):
        self.app        = app
        self.window     = None
        self._prev_hwnd = None
        self._thinking  = None

    def show(self, selected_text: str):
        self.hide()
        if not selected_text.strip():
            self.app.tooltip.show(
                "⚠️ No se detectó texto seleccionado.\n"
                "Selecciona texto y usa Win+Alt+E.", "warning"
            )
            return

        self._prev_hwnd = ctypes.windll.user32.GetForegroundWindow()

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

        # ── Acciones principales ───────────────────────────────────────
        main_actions = [a for a in AI_ACTIONS if a.get("section") == "Texto y Contenido"]
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

        # ── Secciones agrupadas (otras) ────────────────────────────────
        sectioned_actions = [a for a in AI_ACTIONS if a.get("section") != "Texto y Contenido"]
        if sectioned_actions:
            sections: dict = {}
            for a in sectioned_actions:
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

        fade_window(win, 0.97, 0.15)
        win.bind("<Escape>", lambda e: self.hide())
        win.bind("<FocusOut>", lambda e: win.after(220, self._check_focus))
        win.focus_force()


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
        thinking = ThinkingWindow(self.app.root, f"{action['label'].strip()}…")
        threading.Thread(
            target=run_ai_action,
            args=(self.app, action["prompt"], text, self._prev_hwnd, thinking),
            daemon=True
        ).start()

    def _on_custom_prompt(self, selected_text: str):
        self.hide()
        CustomPromptWindow(self.app, selected_text, self._prev_hwnd)



# ─────────────────────────────────────────────────────────────
# Ventana de Prompt Personalizado
# ─────────────────────────────────────────────────────────────
class CustomPromptWindow:
    """Permite al usuario escribir un prompt libre para aplicar al texto."""

    def __init__(self, app: EscribaApp, selected_text: str, prev_hwnd):
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
            target=run_ai_action,
            args=(self.app, action["prompt"], self.selected_text, self.prev_hwnd, thinking),
            daemon=True
        ).start()



# ─────────────────────────────────────────────────────────────
# Ventana de Resultado con botón Sustituir
# ─────────────────────────────────────────────────────────────
class ResultWindow:
    """Muestra el resultado de la IA con opciones de copiar, sustituir y regenerar."""

    _last_pollinations_ts: float = 0.0
    _POLLINATIONS_COOLDOWN = 10  # segundos

    def __init__(self, app: EscribaApp, result: str, prev_hwnd,
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

        # Badge del backend
        badge_text = "⚡ Gemini" if used_gemini else "🌐 Pollinations (gratuito)"
        badge_style = "info" if used_gemini else "warning"
        tb.Label(hdr, text=badge_text, font=("Segoe UI", 9), bootstyle=badge_style).pack(side=RIGHT)

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

        if has_prompt and not used_gemini:
            self._start_cooldown()

        tb.Button(btn_mid, text="⬅️  Sustituir texto seleccionado",
                  bootstyle="info",
                  command=self._replace).pack(side=LEFT, expand=True, fill=X, ipady=4)

        # Área de texto editable
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
        threading.Thread(
            target=self._do_replace, args=(text,), daemon=True
        ).start()

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
        run_ai_action(self.app, self.prompt, self.selected_text, self.prev_hwnd, thinking)
