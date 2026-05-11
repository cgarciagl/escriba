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
# Paleta FloatingMenu
# ─────────────────────────────────────────────────────────────
_FM_BG     = "#151a26"   # fondo principal
_FM_CARD   = "#1e2436"   # fondo botón/card
_FM_HOVER  = "#28304a"   # hover de botón
_FM_ACCENT = "#f59e0b"   # ámbar acento
_FM_TEXT   = "#e2e8f0"   # texto principal (blanco)
_FM_MUTED  = "#64748b"   # texto secundario
_FM_BADGE  = "#0f1320"   # fondo badge de atajo
_FM_SEP    = "#252d42"   # línea separadora


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


def position_bottom_right(window, margin_x=22, margin_y=110):
    """Posiciona la ventana en la esquina inferior derecha (DRY)."""
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    w = window.winfo_reqwidth()
    h = window.winfo_reqheight()
    window.geometry(f"+{sw - w - margin_x}+{sh - h - margin_y}")


def run_ai_action(app, prompt, text, prev_hwnd, thinking):
    """Ejecuta una acción de IA en hilo secundario."""
    def close():
        thinking.close()
    try:
        result, used_gemini = generate_with_fallback(prompt, text)
        app.schedule(close)
        app.schedule(lambda: ResultWindow(
            app, result, prev_hwnd,
            prompt=prompt, selected_text=text,
            used_gemini=used_gemini))
    except Exception as e:
        app.schedule(close)
        app.schedule(app.tooltip.show, f"❌ {str(e)[:180]}", "danger", 6000)


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
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        win.configure(bg=_FM_BG)
        win.option_add('*Label.foreground', _FM_TEXT, 'userDefault')
        win.option_add('*Label.background', _FM_BG, 'userDefault')
        win.option_add('*Frame.background', _FM_BG, 'userDefault')
        self.window = win

        border_color = {
            "info": _FM_ACCENT, "warning": "#f59e0b",
            "danger": "#ef4444", "success": "#22c55e",
        }.get(style, _FM_ACCENT)
        outer = tk.Frame(win, bg=border_color, padx=2, pady=2)
        outer.pack(fill=BOTH, expand=True)
        inner = tk.Frame(outer, bg=_FM_BG, padx=14, pady=10)
        inner.pack(fill=BOTH, expand=True)
        tk.Label(inner, text=message, font=("Segoe UI", 10),
                 bg=_FM_BG, fg=_FM_TEXT, wraplength=370, justify=LEFT).pack()

        win.update_idletasks()
        position_bottom_right(win, margin_y=110)
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
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        win.configure(bg=_FM_BG)
        win.option_add('*Label.foreground', _FM_TEXT, 'userDefault')
        win.option_add('*Label.background', _FM_BG, 'userDefault')
        win.option_add('*Frame.background', _FM_BG, 'userDefault')
        self.window = win

        outer = tk.Frame(win, bg=_FM_ACCENT, padx=2, pady=2)
        outer.pack(fill=BOTH, expand=True)
        inner = tk.Frame(outer, bg=_FM_BG, padx=16, pady=12)
        inner.pack(fill=BOTH, expand=True)

        hdr = tk.Frame(inner, bg=_FM_BG)
        hdr.pack(fill=X, pady=(0, 6))
        badge = tk.Frame(hdr, bg=_FM_ACCENT, padx=6, pady=4)
        badge.pack(side=LEFT, padx=(0, 8))
        tk.Label(badge, text="⚡︎", font=("Segoe UI", 10, "bold"),
                 bg=_FM_ACCENT, fg=_FM_BG).pack()
        tk.Label(hdr, text=APP_NAME, font=("Segoe UI", 10, "bold"),
                 bg=_FM_BG, fg=_FM_TEXT).pack(side=LEFT)

        tk.Label(inner, text=label, font=("Segoe UI", 9),
                 bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W, pady=(0, 10))

        bar = tb.Progressbar(inner, mode="indeterminate",
                             bootstyle="warning-striped", length=240)
        bar.pack(fill=X)
        bar.start(10)
        self._bar = bar

        position_bottom_right(win)
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
    """Banner de bienvenida en la esquina inferior-derecha."""
    _HOLD_MS = 2800

    def __init__(self, root: tb.Window):
        self.root   = root
        self.window = None
        self.root.after(300, self._show)

    def _show(self):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        win.configure(bg=_FM_BG)
        win.option_add('*Label.foreground', _FM_TEXT, 'userDefault')
        win.option_add('*Label.background', _FM_BG, 'userDefault')
        win.option_add('*Frame.background', _FM_BG, 'userDefault')
        self.window = win

        outer = tk.Frame(win, bg=_FM_ACCENT, padx=2, pady=2)
        outer.pack(fill=BOTH, expand=True)
        inner = tk.Frame(outer, bg=_FM_BG, padx=18, pady=14)
        inner.pack(fill=BOTH, expand=True)

        hdr = tk.Frame(inner, bg=_FM_BG)
        hdr.pack(fill=X, pady=(0, 10))
        badge = tk.Frame(hdr, bg=_FM_ACCENT, padx=12, pady=10)
        badge.pack(side=LEFT, padx=(0, 12))
        tk.Label(badge, text="⚡", font=("Segoe UI Emoji", 18),
                 bg=_FM_ACCENT, fg=_FM_BG).pack()
        title_col = tk.Frame(hdr, bg=_FM_BG)
        title_col.pack(side=LEFT)
        tk.Label(title_col, text=APP_NAME,
                 font=("Segoe UI", 16, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(anchor=W)
        tk.Label(title_col, text="Asistente de Texto con IA",
                 font=("Segoe UI", 9), bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W)

        tk.Frame(inner, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 10))

        hint_row = tk.Frame(inner, bg=_FM_BG)
        hint_row.pack(fill=X)
        tk.Label(hint_row, text="Atajo: ", font=("Segoe UI", 9),
                 bg=_FM_BG, fg=_FM_MUTED).pack(side=LEFT)
        tk.Label(hint_row, text="Win + Alt + E",
                 font=("Consolas", 9, "bold"), bg=_FM_BG, fg=_FM_ACCENT).pack(side=LEFT)

        position_bottom_right(win)
        fade_window(win, 0.95, 0.12)
        win.after(self._HOLD_MS, lambda: fade_window(win, 0.0, -0.07,
                  on_done=lambda: win.destroy() if win.winfo_exists() else None))



# ─────────────────────────────────────────────────────────────
# Ventana de Configuración
# ─────────────────────────────────────────────────────────────
class ConfigWindow:
    """Formulario para API Key, autostart y configuración general."""

    def __init__(self, app: EscribaApp):
        self.app = app
        self.window = None

    def show(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        win = tb.Toplevel(self.app.root)
        win.title(f"{APP_NAME} — Configuración")
        win.geometry("520x560")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.configure(bg=_FM_BG)
        win.option_add('*Label.foreground', _FM_TEXT, 'userDefault')
        win.option_add('*Label.background', _FM_BG, 'userDefault')
        win.option_add('*Frame.background', _FM_BG, 'userDefault')
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{(sw-520)//2}+{(sh-500)//2}")
        self.window = win

        frame = tk.Frame(win, bg=_FM_BG, padx=30, pady=24)
        frame.pack(fill=BOTH, expand=True)

        # ── Header ──────────────────────────────────────────
        hdr = tk.Frame(frame, bg=_FM_BG)
        hdr.pack(fill=X, pady=(0, 4))
        badge = tk.Frame(hdr, bg=_FM_ACCENT, padx=10, pady=8)
        badge.pack(side=LEFT, padx=(0, 12))
        tk.Label(badge, text="⚡︎", font=("Segoe UI", 16, "bold"),
                 bg=_FM_ACCENT, fg=_FM_BG).pack()
        title_col = tk.Frame(hdr, bg=_FM_BG)
        title_col.pack(side=LEFT)
        tk.Label(title_col, text=APP_NAME,
                 font=("Segoe UI", 14, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(anchor=W)
        tk.Label(title_col, text="Configuración",
                 font=("Segoe UI", 9), bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W)
        tk.Frame(frame, bg=_FM_SEP, height=1).pack(fill=X, pady=(10, 20))

        # ── API Key ──────────────────────────────────────────
        tk.Label(frame, text="API Key de Google Gemini",
                 font=("Segoe UI", 10, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(anchor=W, pady=(0, 6))

        self.api_key_var = tk.StringVar(value=ConfigManager.get_api_key())
        key_entry = tb.Entry(frame, textvariable=self.api_key_var,
                             show="•", font=("Consolas", 11), bootstyle="warning")
        key_entry.pack(fill=X, ipady=6, pady=(0, 6))

        url_label = tk.Label(frame,
                             text="Obtén tu clave en → https://aistudio.google.com/apikey",
                             font=("Segoe UI", 9), bg=_FM_BG, fg=_FM_MUTED, cursor="hand2")
        url_label.pack(anchor=W, pady=(0, 20))
        url_label.bind("<Button-1>", lambda e: webbrowser.open("https://aistudio.google.com/apikey"))

        # ── Hotkey Info ──────────────────────────────────────
        tk.Frame(frame, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 14))
        hotkey_row = tk.Frame(frame, bg=_FM_BG)
        hotkey_row.pack(fill=X, pady=(0, 14))
        tk.Label(hotkey_row, text="Atajo global:  ",
                 font=("Segoe UI", 10, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(side=LEFT)
        tk.Label(hotkey_row, text="Win + Alt + E",
                 font=("Consolas", 10), bg=_FM_BG, fg=_FM_ACCENT).pack(side=LEFT)

        # ── Arranque con Windows ─────────────────────────────
        tk.Frame(frame, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 14))
        self.autostart_var = tk.BooleanVar(value=StartupManager.is_enabled())
        autostart_chk = tb.Checkbutton(
            frame,
            text="  Iniciar automáticamente con Windows",
            variable=self.autostart_var,
            bootstyle="warning-round-toggle",
        )
        autostart_chk.pack(anchor=W, pady=(0, 20))

        # ── Status label ─────────────────────────────────────
        self.status_var = tk.StringVar()
        self.status_lbl = tk.Label(frame, textvariable=self.status_var,
                                   font=("Segoe UI", 9), wraplength=460,
                                   bg=_FM_BG, fg=_FM_MUTED)
        self.status_lbl.pack(anchor=W, pady=(0, 10))

        # ── Botón Guardar ────────────────────────────────────
        tb.Button(frame, text="💾  Guardar y Cerrar",
                  bootstyle="warning", width=26,
                  command=self._save).pack()

        key_entry.focus_set()
        win.bind("<Return>", lambda e: self._save())
        win.protocol("WM_DELETE_WINDOW", self._close)

    def _save(self):
        key = self.api_key_var.get().strip()
        ConfigManager.set("api_key", key)
        if self.autostart_var.get():
            StartupManager.enable()
        else:
            StartupManager.disable()
        ConfigManager.set("autostart", self.autostart_var.get())

        self.status_var.set("✅  Configuración guardada correctamente.")
        self.status_lbl.configure(fg=_FM_ACCENT)
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
        self.app = app
        self.window = None
        self._prev_hwnd = None

    def _action_btn(self, parent: tk.Widget, action: dict, cmd) -> tk.Frame:
        """Card-style button: icono + texto + badge de atajo. El caller hace grid()."""
        shortcut = action.get("shortcut", "")

        frame = tk.Frame(parent, bg=_FM_CARD, cursor="hand2")
        inner = tk.Frame(frame, bg=_FM_CARD, padx=10, pady=9)
        inner.pack(fill=X)

        parts = action["label"].split("  ", 1)
        icon = parts[0].strip() if len(parts) == 2 else ""
        text = parts[1].strip() if len(parts) == 2 else action["label"].strip()

        icon_lbl = tk.Label(inner, text=icon, font=("Segoe UI Emoji", 12),
                            bg=_FM_CARD, fg=_FM_ACCENT)
        icon_lbl.pack(side=LEFT, padx=(0, 6))

        text_lbl = tk.Label(inner, text=text, font=("Segoe UI", 9),
                            bg=_FM_CARD, fg=_FM_TEXT, anchor=W)
        text_lbl.pack(side=LEFT, fill=X, expand=True)

        badge_clickable = []
        if shortcut:
            badge_f = tk.Frame(inner, bg=_FM_BADGE)
            badge_f.pack(side=RIGHT)
            badge_lbl = tk.Label(badge_f, text=shortcut, font=("Segoe UI", 7),
                                 bg=_FM_BADGE, fg=_FM_MUTED, padx=5, pady=2)
            badge_lbl.pack()
            badge_clickable = [badge_f, badge_lbl]

        card_ws = [frame, inner, icon_lbl, text_lbl]

        def _enter(e):
            mx, my = frame.winfo_pointerx(), frame.winfo_pointery()
            rx, ry = frame.winfo_rootx(), frame.winfo_rooty()
            if rx <= mx <= rx + frame.winfo_width() and ry <= my <= ry + frame.winfo_height():
                for w in card_ws:
                    w.configure(bg=_FM_HOVER)

        def _leave(e):
            mx, my = frame.winfo_pointerx(), frame.winfo_pointery()
            rx, ry = frame.winfo_rootx(), frame.winfo_rooty()
            if not (rx <= mx <= rx + frame.winfo_width() and ry <= my <= ry + frame.winfo_height()):
                for w in card_ws:
                    w.configure(bg=_FM_CARD)

        for w in card_ws + badge_clickable:
            w.bind("<Button-1>", lambda e, c=cmd: c())
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)

        return frame

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

        win = tk.Toplevel(self.app.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        win.configure(bg=_FM_BG)
        # Defensa contra override del tema vapor en tk.Label
        win.option_add('*Label.foreground', _FM_TEXT, 'userDefault')
        win.option_add('*Label.background', _FM_BG, 'userDefault')
        win.option_add('*Frame.background', _FM_BG, 'userDefault')
        self.window = win

        outer = tk.Frame(win, bg=_FM_BG, padx=16, pady=14)
        outer.pack(fill=BOTH, expand=True)

        # ── Header ──────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg=_FM_BG)
        hdr.pack(fill=X, pady=(0, 10))

        badge_frame = tk.Frame(hdr, bg=_FM_ACCENT, padx=10, pady=8)
        badge_frame.pack(side=LEFT, padx=(0, 12))
        tk.Label(badge_frame, text="⚡︎", font=("Segoe UI", 16, "bold"),
                 bg=_FM_ACCENT, fg=_FM_BG).pack()

        title_col = tk.Frame(hdr, bg=_FM_BG)
        title_col.pack(side=LEFT, fill=Y, expand=True)
        tk.Label(title_col, text=APP_NAME, font=("Segoe UI", 14, "bold"),
                 bg=_FM_BG, fg=_FM_TEXT, anchor=W).pack(anchor=W)
        word_count = len(selected_text.split())
        char_count  = len(selected_text.strip())
        tk.Label(title_col, text=f"{word_count} pal  ·  {char_count} car",
                 font=("Segoe UI", 8), bg=_FM_BG, fg=_FM_MUTED, anchor=W).pack(anchor=W)

        close_lbl = tk.Label(hdr, text="×", font=("Segoe UI", 16),
                             bg=_FM_BG, fg=_FM_MUTED, cursor="hand2")
        close_lbl.pack(side=RIGHT, anchor=N)
        close_lbl.bind("<Button-1>", lambda e: self.hide())

        # ── Separator ────────────────────────────────────────────────────
        tk.Frame(outer, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 12))

        # ── Preview card ─────────────────────────────────────────────────
        preview = selected_text[:100] + ("…" if len(selected_text) > 100 else "")
        _PREVIEW_BG = "#0a0e1a"  # más oscuro que _FM_BG para destacar
        card_border = tk.Frame(outer, bg=_FM_ACCENT, padx=2, pady=2)
        card_border.pack(fill=X, pady=(0, 14))
        card_content = tk.Frame(card_border, bg=_PREVIEW_BG, padx=12, pady=10)
        card_content.pack(fill=BOTH, expand=True)
        sel_hdr = tk.Frame(card_content, bg=_PREVIEW_BG)
        sel_hdr.pack(fill=X, pady=(0, 4))
        tk.Label(sel_hdr, text="▤", font=("Segoe UI", 9, "bold"),
                 bg=_PREVIEW_BG, fg=_FM_ACCENT).pack(side=LEFT, padx=(0, 6))
        tk.Label(sel_hdr, text="SELECCIÓN", font=("Segoe UI", 8, "bold"),
                 bg=_PREVIEW_BG, fg=_FM_ACCENT).pack(side=LEFT)
        tk.Label(card_content, text=preview, font=("Consolas", 9),
                 bg=_PREVIEW_BG, fg=_FM_TEXT, wraplength=310, justify=LEFT).pack(anchor=W)

        # ── Acciones por sección ──────────────────────────────────────────
        all_sections: dict = {}
        for a in AI_ACTIONS:
            all_sections.setdefault(a.get("section", ""), []).append(a)

        for i, (sec_name, sec_actions) in enumerate(all_sections.items()):
            if i > 0:
                tk.Frame(outer, bg=_FM_SEP, height=1).pack(fill=X, pady=(4, 12))

            sec_row = tk.Frame(outer, bg=_FM_BG)
            sec_row.pack(fill=X, pady=(0, 8))
            tk.Label(sec_row, text=sec_name.upper(), font=("Segoe UI", 7, "bold"),
                     bg=_FM_BG, fg=_FM_MUTED).pack(side=LEFT)
            tk.Frame(sec_row, bg=_FM_SEP, height=1).pack(
                side=LEFT, fill=X, expand=True, padx=(8, 0), pady=(4, 0))

            sec_grid = tk.Frame(outer, bg=_FM_BG)
            sec_grid.pack(fill=X, pady=(0, 4))
            sec_grid.columnconfigure(0, weight=1)
            sec_grid.columnconfigure(1, weight=1)

            for j, action in enumerate(sec_actions):
                row, col = divmod(j, 2)
                span = 2 if (j == len(sec_actions) - 1 and len(sec_actions) % 2 != 0) else 1
                btn = self._action_btn(sec_grid, action,
                                       lambda a=action: self._on_action(a, selected_text))
                btn.grid(row=row, column=col, columnspan=span, sticky="ew",
                         padx=(0, 4) if col == 0 else (4, 0), pady=3)

        # ── CTA ──────────────────────────────────────────────────────────
        tk.Frame(outer, bg=_FM_SEP, height=1).pack(fill=X, pady=(8, 12))

        cta = tk.Frame(outer, bg=_FM_ACCENT, cursor="hand2")
        cta.pack(fill=X)
        cta_inner = tk.Frame(cta, bg=_FM_ACCENT, padx=14, pady=11)
        cta_inner.pack(fill=X)
        cta_icon = tk.Label(cta_inner, text="✦", font=("Segoe UI Emoji", 11),
                            bg=_FM_ACCENT, fg=_FM_BG)
        cta_icon.pack(side=LEFT, padx=(0, 8))
        cta_lbl = tk.Label(cta_inner, text="Crear prompt personalizado",
                           font=("Segoe UI", 10, "bold"), bg=_FM_ACCENT, fg=_FM_BG)
        cta_lbl.pack(side=LEFT)
        cta_badge = tk.Frame(cta_inner, bg="#d18a0a")
        cta_badge.pack(side=RIGHT)
        cta_badge_lbl = tk.Label(cta_badge, text="Ctrl+K", font=("Segoe UI", 7, "bold"),
                                 bg="#d18a0a", fg=_FM_BG, padx=6, pady=3)
        cta_badge_lbl.pack()
        cta_cmd = lambda: self._on_custom_prompt(selected_text)
        for w in [cta, cta_inner, cta_icon, cta_lbl, cta_badge, cta_badge_lbl]:
            w.bind("<Button-1>", lambda e: cta_cmd())

        # ── Atajos de teclado ─────────────────────────────────────────────
        for action in AI_ACTIONS:
            key = action.get("shortcut_key", "")
            if key:
                win.bind(key, lambda e, a=action: self._on_action(a, selected_text))
        win.bind("<Control-k>", lambda e: self._on_custom_prompt(selected_text))

        # ── Posición y fade ───────────────────────────────────────────────
        win.minsize(390, 100)
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = mouse_x + 14 if mouse_x + 14 + w < sw else mouse_x - w - 14
        y = mouse_y + 14 if mouse_y + 14 + h < sh else mouse_y - h - 14
        win.geometry(f"+{x}+{y}")

        fade_window(win, 0.96, 0.15)
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
        self.app = app
        self.selected_text = selected_text
        self.prev_hwnd = prev_hwnd

        win = tb.Toplevel(app.root)
        win.title(f"{APP_NAME} — Prompt personalizado")
        win.attributes("-topmost", True)
        win.resizable(True, True)
        win.configure(bg=_FM_BG)
        win.option_add('*Label.foreground', _FM_TEXT, 'userDefault')
        win.option_add('*Label.background', _FM_BG, 'userDefault')
        win.option_add('*Frame.background', _FM_BG, 'userDefault')
        self.window = win

        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = 520, 340
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        frame = tk.Frame(win, bg=_FM_BG, padx=16, pady=12)
        frame.pack(fill=BOTH, expand=True)

        tk.Label(frame, text="✦  Escribe tu prompt",
                 font=("Segoe UI", 12, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(anchor=W, pady=(0, 4))

        preview = selected_text[:75] + ("…" if len(selected_text) > 75 else "")
        tk.Label(frame, text=f'Texto seleccionado: "{preview}"',
                 font=("Segoe UI", 9, "italic"),
                 bg=_FM_BG, fg=_FM_MUTED, wraplength=480).pack(anchor=W, pady=(0, 8))

        tk.Frame(frame, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 8))

        btn_frame = tk.Frame(frame, bg=_FM_BG)
        btn_frame.pack(side=BOTTOM, fill=X, pady=(8, 0))
        tb.Button(btn_frame, text="🚀  Ejecutar",
                  bootstyle="warning",
                  command=self._execute).pack(side=LEFT, expand=True, fill=X, padx=(0, 6), ipady=4)
        tb.Button(btn_frame, text="✕  Cancelar",
                  bootstyle="secondary-outline",
                  command=win.destroy).pack(side=LEFT, expand=True, fill=X, ipady=4)

        txt_frame = tk.Frame(frame, bg=_FM_BG)
        txt_frame.pack(fill=BOTH, expand=True)

        scrollbar = tb.Scrollbar(txt_frame, bootstyle="warning-round")
        scrollbar.pack(side=RIGHT, fill=Y)

        self.prompt_widget = tk.Text(
            txt_frame,
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            relief="flat",
            bg=_FM_CARD, fg=_FM_TEXT,
            insertbackground=_FM_ACCENT,
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
        self.app = app
        self.result = result
        self.prev_hwnd = prev_hwnd
        self.prompt = prompt
        self.selected_text = selected_text
        self.used_gemini = used_gemini

        if not used_gemini:
            ResultWindow._last_pollinations_ts = time.time()

        win = tb.Toplevel(app.root)
        win.title(f"{APP_NAME} — Resultado")
        win.attributes("-topmost", True)
        win.resizable(True, True)
        win.configure(bg=_FM_BG)
        win.option_add('*Label.foreground', _FM_TEXT, 'userDefault')
        win.option_add('*Label.background', _FM_BG, 'userDefault')
        win.option_add('*Frame.background', _FM_BG, 'userDefault')
        self.window = win

        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w, h = 580, 420
        win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        frame = tk.Frame(win, bg=_FM_BG, padx=16, pady=12)
        frame.pack(fill=BOTH, expand=True)

        # Header
        hdr = tk.Frame(frame, bg=_FM_BG)
        hdr.pack(fill=X, pady=(0, 8))
        tk.Label(hdr, text="✦  Texto generado",
                 font=("Segoe UI", 12, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(side=LEFT)

        # Badge del backend
        badge_text = "⚡ Gemini" if used_gemini else "🌐 Pollinations"
        badge_bg = _FM_ACCENT if used_gemini else _FM_CARD
        badge_fg = _FM_BG if used_gemini else _FM_MUTED
        badge_f = tk.Frame(hdr, bg=badge_bg)
        badge_f.pack(side=RIGHT)
        tk.Label(badge_f, text=badge_text, font=("Segoe UI", 8),
                 bg=badge_bg, fg=badge_fg, padx=7, pady=3).pack()

        tk.Frame(frame, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 10))

        # Botones — se empaquetan primero con side=BOTTOM para garantizar visibilidad
        btn_bot = tk.Frame(frame, bg=_FM_BG)
        btn_bot.pack(side=BOTTOM, fill=X, pady=(6, 0))

        tb.Button(btn_bot, text="📋  Copiar al portapapeles",
                  bootstyle="secondary-outline",
                  command=self._copy).pack(side=LEFT, expand=True, fill=X, padx=(0, 6), ipady=4)

        tb.Button(btn_bot, text="✕  Cerrar",
                  bootstyle="danger-outline",
                  command=win.destroy).pack(side=LEFT, expand=True, fill=X, ipady=4)

        btn_mid = tk.Frame(frame, bg=_FM_BG)
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
                  bootstyle="warning",
                  command=self._replace).pack(side=LEFT, expand=True, fill=X, ipady=4)

        # Área de texto editable
        txt_frame = tk.Frame(frame, bg=_FM_BG)
        txt_frame.pack(fill=BOTH, expand=True, pady=(0, 6))

        scrollbar = tb.Scrollbar(txt_frame, bootstyle="warning-round")
        scrollbar.pack(side=RIGHT, fill=Y)

        self.text_widget = tk.Text(
            txt_frame,
            font=("Segoe UI", 10),
            wrap=tk.WORD,
            relief="flat",
            bg=_FM_CARD, fg=_FM_TEXT,
            insertbackground=_FM_ACCENT,
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
            self.app.schedule(lambda: self.app.tooltip.show(f"❌ Error al sustituir: {e}", "danger"))

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
