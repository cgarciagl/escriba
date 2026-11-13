"""
Escriba — Elementos comunes de la interfaz.

Paleta de colores, helpers de ventana y las ventanas pequeñas:
TooltipNotification, ThinkingWindow y SplashBanner.
"""

from __future__ import annotations

import tkinter as tk

import ttkbootstrap as tb
from ttkbootstrap.constants import *

import os
from constants import APP_NAME, BASE_DIR
from plataforma import HOTKEY_LABEL, IS_LINUX, IS_MAC, clamp_to_area, monitor_workarea

# Fuentes del sistema (Segoe UI no existe en macOS ni en Linux)
if IS_MAC:
    UI_FONT, EMOJI_FONT, MONO_FONT = "Helvetica Neue", "Apple Color Emoji", "Menlo"
elif IS_LINUX:
    UI_FONT, EMOJI_FONT, MONO_FONT = "DejaVu Sans", "Noto Color Emoji", "DejaVu Sans Mono"
else:
    UI_FONT, EMOJI_FONT, MONO_FONT = "Segoe UI", "Segoe UI Emoji", "Consolas"


# ─────────────────────────────────────────────────────────────
# Paleta FloatingMenu
# ─────────────────────────────────────────────────────────────
_FM_BG     = "#151a26"   # fondo principal
_FM_CARD   = "#1e2436"   # fondo botón/card
_FM_HOVER  = "#28304a"   # hover de botón
_FM_ACCENT = "#f59e0b"   # ámbar acento
_FM_TEXT   = "#e2e8f0"   # texto principal (blanco)
_FM_MUTED  = "#94a3b8"   # texto secundario (contraste ≈ 7:1 sobre _FM_BG)
_FM_BADGE  = "#0f1320"   # fondo badge de atajo
_FM_SEP    = "#252d42"   # línea separadora
_FM_BORDER = "#2a3350"   # borde de ventanas y controles
_FM_DANGER = "#ef4444"
_FM_SUCCESS = "#22c55e"

_STYLE_COLORS = {"info": _FM_ACCENT, "warning": _FM_ACCENT, "danger": _FM_DANGER, "success": _FM_SUCCESS}


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
    ico_path = os.path.join(BASE_DIR, "escriba.ico")
    if os.path.exists(ico_path) and hasattr(window, "iconbitmap"):
        try:
            window.iconbitmap(ico_path)
        except Exception:
            pass


def scale_factor(widget) -> float:
    """Factor de escala de la pantalla (1.0 = 96 ppp; 1.5 con escalado al 150 %)."""
    try:
        return max(1.0, float(widget.winfo_fpixels("1i")) / 96.0)
    except Exception:
        return 1.0


def scaled(widget, pixels: int) -> int:
    """Convierte píxeles de diseño (a 96 ppp) a píxeles reales de la pantalla."""
    return int(round(pixels * scale_factor(widget)))


def center_window(window, width: int, height: int):
    """Fija el tamaño de la ventana (escalado por DPI) y la centra en la pantalla."""
    window.update_idletasks()
    width, height = scaled(window, width), scaled(window, height)
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    window.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 2}")


def place_near_pointer(window, offset: int = 14):
    """Coloca la ventana junto al puntero, sin salirse del monitor donde está."""
    window.update_idletasks()
    px, py = window.winfo_pointerx(), window.winfo_pointery()
    w, h = window.winfo_reqwidth(), window.winfo_reqheight()
    area = monitor_workarea(px, py) or (
        0, 0, window.winfo_screenwidth(), window.winfo_screenheight() - scaled(window, 40)
    )
    x, y = clamp_to_area(px + offset, py + offset, w, h, area)
    window.geometry(f"+{x}+{y}")


# ─────────────────────────────────────────────────────────────
# Tooltip / Notificación flotante
# ─────────────────────────────────────────────────────────────
class TooltipNotification:
    """Notificación flotante en la esquina inferior derecha.

    - Los avisos informativos desaparecen solos.
    - Los errores (style="danger") se quedan hasta que el usuario los cierra.
    - `action=("Texto del botón", callback)` añade un botón que lleva al arreglo.
    """

    def __init__(self, root: tb.Window):
        self.root   = root
        self.window = None

    def show(self, message: str, style: str = "info", duration: int | None = 3500,
             action: tuple[str, callable] | None = None):
        self.hide()
        if style == "danger":
            duration = None  # los errores no desaparecen solos

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        apply_dark_style(win)
        self.window = win

        color = _STYLE_COLORS.get(style, _FM_ACCENT)
        outer = tk.Frame(win, bg=color, padx=2, pady=2)
        outer.pack(fill=BOTH, expand=True)
        inner = tk.Frame(outer, bg=_FM_BG, padx=14, pady=10)
        inner.pack(fill=BOTH, expand=True)

        row = tk.Frame(inner, bg=_FM_BG)
        row.pack(fill=X)
        tk.Label(row, text=message, font=(UI_FONT, 10), bg=_FM_BG, fg=_FM_TEXT,
                 wraplength=scaled(win, 360), justify=LEFT).pack(side=LEFT, anchor=NW)
        close = tk.Label(row, text="✕", font=(UI_FONT, 10), bg=_FM_BG, fg=_FM_MUTED, cursor="hand2")
        close.pack(side=RIGHT, anchor=NE, padx=(10, 0))
        close.bind("<Button-1>", lambda e: self.hide())

        if action:
            label, callback = action

            def run_action():
                self.hide()
                callback()

            tb.Button(inner, text=label, bootstyle="warning-outline",
                      command=run_action).pack(anchor=E, pady=(10, 0))

        win.update_idletasks()
        position_bottom_right(win, margin_y=scaled(win, 110))
        fade_window(win, 0.97, 0.15)
        if duration:
            win.after(duration, lambda: fade_window(win, 0.0, -0.10, on_done=self.hide))

    def hide(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.window = None


# ─────────────────────────────────────────────────────────────
# Ventana de "Pensando…" con barra animada
# ─────────────────────────────────────────────────────────────
class ThinkingWindow:
    """Indicador de progreso mientras la IA trabaja, con botón para cancelar."""

    def __init__(self, root: tb.Window, label: str, on_cancel=None):
        self.root   = root
        self.window = None
        self._bar   = None
        self._label = None
        self._on_cancel = on_cancel
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
        tk.Label(badge, text="⚡︎", font=(UI_FONT, 10, "bold"),
                 bg=_FM_ACCENT, fg=_FM_BG).pack()
        tk.Label(hdr, text=APP_NAME, font=(UI_FONT, 10, "bold"),
                 bg=_FM_BG, fg=_FM_TEXT).pack(side=LEFT)
        if self._on_cancel:
            cancel = tk.Label(hdr, text="Cancelar", font=(UI_FONT, 9, "underline"),
                              bg=_FM_BG, fg=_FM_MUTED, cursor="hand2")
            cancel.pack(side=RIGHT)
            cancel.bind("<Button-1>", lambda e: self.cancel())

        self._label = tk.Label(inner, text=label, font=(UI_FONT, 9),
                               bg=_FM_BG, fg=_FM_MUTED)
        self._label.pack(anchor=W, pady=(0, 10))

        bar = tb.Progressbar(inner, mode="indeterminate",
                             bootstyle="warning-striped", length=scaled(win, 260))
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

    def cancel(self):
        if self._label and self.window and self.window.winfo_exists():
            self._label.config(text="Cancelando…")
        if self._on_cancel:
            self._on_cancel()

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
        tk.Label(badge, text="⚡", font=(EMOJI_FONT, 18),
                 bg=_FM_ACCENT, fg=_FM_BG).pack()
        title_col = tk.Frame(hdr, bg=_FM_BG)
        title_col.pack(side=LEFT)
        tk.Label(title_col, text=APP_NAME,
                 font=(UI_FONT, 16, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(anchor=W)
        tk.Label(title_col, text="Asistente de Texto con IA",
                 font=(UI_FONT, 9), bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W)

        tk.Frame(inner, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 10))

        hint_row = tk.Frame(inner, bg=_FM_BG)
        hint_row.pack(fill=X)
        tk.Label(hint_row, text="Atajo: ", font=(UI_FONT, 9),
                 bg=_FM_BG, fg=_FM_MUTED).pack(side=LEFT)
        tk.Label(hint_row, text=HOTKEY_LABEL,
                 font=(MONO_FONT, 9, "bold"), bg=_FM_BG, fg=_FM_ACCENT).pack(side=LEFT)

        position_bottom_right(win)
        fade_window(win, 0.95, 0.12)
        win.after(self._HOLD_MS, lambda: fade_window(win, 0.0, -0.07,
                  on_done=lambda: win.destroy() if win.winfo_exists() else None))


# ─────────────────────────────────────────────────────────────
# Estilos ttk con la paleta de Escriba
# (el tema "vapor" pinta campos y botones secundarios en morado/rosa/cian)
# ─────────────────────────────────────────────────────────────
_FM_DISABLED = "#4b5563"


def configure_styles(root):
    """Registra los estilos "Escriba.*". Llamar una vez tras crear la ventana raíz."""
    style = tb.Style()
    flat = dict(bordercolor=_FM_BORDER, darkcolor=_FM_CARD, lightcolor=_FM_CARD, relief="flat")

    # Botón secundario
    style.configure("Escriba.TButton", background=_FM_CARD, foreground=_FM_TEXT,
                    focuscolor=_FM_ACCENT, padding=(10, 5), font=(UI_FONT, 9), **flat)
    style.map("Escriba.TButton",
              background=[("disabled", _FM_BG), ("pressed", _FM_HOVER), ("active", _FM_HOVER)],
              foreground=[("disabled", _FM_DISABLED)],
              bordercolor=[("disabled", _FM_SEP), ("active", _FM_ACCENT), ("focus", _FM_ACCENT)])

    # Selector segmentado (Resultado / Original)
    style.configure("Escriba.Toolbutton", background=_FM_CARD, foreground=_FM_MUTED,
                    padding=(12, 4), font=(UI_FONT, 9), **flat)
    style.map("Escriba.Toolbutton",
              background=[("selected", _FM_ACCENT), ("active", _FM_HOVER)],
              foreground=[("selected", _FM_BG), ("active", _FM_TEXT)])

    # Campos de texto y listas desplegables
    style.configure("Escriba.TEntry", fieldbackground=_FM_CARD, foreground=_FM_TEXT,
                    insertcolor=_FM_ACCENT, padding=6, bordercolor=_FM_BORDER,
                    lightcolor=_FM_BORDER, darkcolor=_FM_BORDER)
    style.map("Escriba.TEntry", bordercolor=[("focus", _FM_ACCENT)], lightcolor=[("focus", _FM_ACCENT)])
    style.configure("Escriba.TCombobox", fieldbackground=_FM_CARD, foreground=_FM_TEXT,
                    background=_FM_CARD, arrowcolor=_FM_MUTED, padding=5, insertcolor=_FM_ACCENT,
                    bordercolor=_FM_BORDER, lightcolor=_FM_BORDER, darkcolor=_FM_BORDER)
    style.map("Escriba.TCombobox",
              fieldbackground=[("readonly", _FM_CARD)], foreground=[("readonly", _FM_TEXT)],
              selectbackground=[("readonly", _FM_CARD)], selectforeground=[("readonly", _FM_TEXT)],
              bordercolor=[("focus", _FM_ACCENT)], lightcolor=[("focus", _FM_ACCENT)])
    root.option_add("*TCombobox*Listbox.background", _FM_CARD)
    root.option_add("*TCombobox*Listbox.foreground", _FM_TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", _FM_HOVER)
    root.option_add("*TCombobox*Listbox.selectForeground", _FM_ACCENT)

    # Pestañas
    style.configure("Escriba.TNotebook", background=_FM_BG, bordercolor=_FM_BORDER,
                    lightcolor=_FM_BG, darkcolor=_FM_BG, tabmargins=(0, 0, 0, 0))
    style.configure("Escriba.TNotebook.Tab", background=_FM_BG, foreground=_FM_MUTED,
                    bordercolor=_FM_BORDER, lightcolor=_FM_BG, darkcolor=_FM_BG,
                    padding=(14, 6), font=(UI_FONT, 9))
    style.map("Escriba.TNotebook.Tab",
              background=[("selected", _FM_CARD), ("active", _FM_HOVER)],
              foreground=[("selected", _FM_ACCENT), ("active", _FM_TEXT)])

    # Barra de desplazamiento
    style.configure("Escriba.Vertical.TScrollbar", troughcolor=_FM_CARD, background=_FM_BORDER,
                    bordercolor=_FM_CARD, lightcolor=_FM_BORDER, darkcolor=_FM_BORDER,
                    arrowcolor=_FM_MUTED, gripcount=0, relief="flat")
    style.map("Escriba.Vertical.TScrollbar", background=[("active", _FM_ACCENT)])

    # Casillas y opciones sobre el fondo de Escriba
    style.configure("Escriba.TRadiobutton", background=_FM_BG, foreground=_FM_TEXT,
                    indicatorcolor=_FM_CARD, font=(UI_FONT, 9))
    style.map("Escriba.TRadiobutton", indicatorcolor=[("selected", _FM_ACCENT)],
              background=[("active", _FM_BG)])
    style.configure("Escriba.TCheckbutton", background=_FM_BG, foreground=_FM_TEXT,
                    indicatorcolor=_FM_CARD, font=(UI_FONT, 9))
    style.map("Escriba.TCheckbutton", indicatorcolor=[("selected", _FM_ACCENT)],
              background=[("active", _FM_BG)])
