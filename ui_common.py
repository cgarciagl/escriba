"""
Escriba — Elementos comunes de la interfaz.

Paleta de colores, helpers de ventana y las ventanas pequeñas:
TooltipNotification, ThinkingWindow y SplashBanner.
"""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from constants import APP_NAME


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


def apply_dark_style(window):
    """Fondo y colores por defecto de las ventanas con la paleta _FM_*."""
    window.configure(bg=_FM_BG)
    window.option_add('*Label.foreground', _FM_TEXT, 'userDefault')
    window.option_add('*Label.background', _FM_BG, 'userDefault')
    window.option_add('*Frame.background', _FM_BG, 'userDefault')


def center_window(window, width: int, height: int):
    """Fija el tamaño de la ventana y la centra en la pantalla."""
    window.update_idletasks()
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    window.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 2}")


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
        apply_dark_style(win)
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
        self._label = None
        self.root.after(0, self._show, label)

    def _show(self, label: str):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        apply_dark_style(win)
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

        self._label = tk.Label(inner, text=label, font=("Segoe UI", 9),
                               bg=_FM_BG, fg=_FM_MUTED)
        self._label.pack(anchor=W, pady=(0, 10))

        bar = tb.Progressbar(inner, mode="indeterminate",
                             bootstyle="warning-striped", length=240)
        bar.pack(fill=X)
        bar.start(10)
        self._bar = bar

        position_bottom_right(win)
        fade_window(win, 0.95, 0.15)

    def update_status(self, text: str):
        """Actualiza el texto descriptivo del progreso en el hilo principal."""
        def _update():
            if self._label and self.window and self.window.winfo_exists():
                self._label.config(text=text)
        self.root.after(0, _update)

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
        apply_dark_style(win)
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
