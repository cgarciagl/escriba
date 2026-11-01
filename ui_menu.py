"""
Escriba — Menú flotante de acciones y ventana de prompt personalizado.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from actions import display_shortcut, load_actions
from constants import APP_NAME
from plataforma import IS_MAC, bring_app_to_front, get_foreground_window, shortcut_label, tk_shortcut
from ui_common import (
    _FM_ACCENT, _FM_BG, _FM_CARD, _FM_MUTED, _FM_SEP, _FM_TEXT, MONO_FONT, UI_FONT,
    apply_dark_style, center_window, fade_window,
)
from ui_result import CUSTOM_PROMPT_LABEL, start_ai_action

if TYPE_CHECKING:
    from escriba import EscribaApp

# Ctrl+Espacio en Windows; ⌘↩ en macOS (⌘Espacio es Spotlight).
CUSTOM_PROMPT_SHORTCUT = (
    ("⌘↩", "<Command-Return>") if IS_MAC else ("Ctrl+Espacio", "<Control-space>")
)
RUN_PROMPT_SHORTCUT = (shortcut_label("Ctrl+Enter"), tk_shortcut("Return"))


def group_by_section(actions: list[dict]) -> list[tuple[str, list[dict]]]:
    """Agrupa las acciones por sección conservando el orden de aparición."""
    groups: dict[str, list[dict]] = {}
    for action in actions:
        groups.setdefault(action.get("section", ""), []).append(action)
    return list(groups.items())


def button_text(action: dict) -> str:
    shortcut = display_shortcut(action["shortcut"]) if action.get("shortcut_key") else ""
    return f"{action['label']}   ·  {shortcut}" if shortcut else action["label"]


# ─────────────────────────────────────────────────────────────
# Menú Flotante de IA
# ─────────────────────────────────────────────────────────────
class FloatingMenu:
    """Menú contextual con las acciones de IA sobre el texto seleccionado."""

    def __init__(self, app: EscribaApp):
        self.app = app
        self.window = None
        self._prev_hwnd = None

    def _add_action_grid(self, parent, actions: list[dict], selected_text: str, ipady: int):
        grid = tb.Frame(parent)
        grid.pack(fill=X, pady=(0, 4))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        for i, action in enumerate(actions):
            row, col = divmod(i, 2)
            span = 2 if (i == len(actions) - 1 and len(actions) % 2 != 0) else 1
            btn = tb.Button(grid, text=button_text(action),
                            bootstyle=action.get("bootstyle", "info-outline"),
                            command=lambda a=action: self._on_action(a, selected_text))
            btn.grid(row=row, column=col, columnspan=span, sticky="ew",
                     padx=(0, 2) if col == 0 else (2, 0), pady=2, ipady=ipady)

    def show(self, selected_text: str):
        self.hide()
        if not selected_text.strip():
            self.app.tooltip.show(
                "⚠️ No se detectó texto seleccionado.\n"
                "Selecciona texto y usa Win+Alt+E.", "warning"
            )
            return

        # Se leen en cada apertura: los cambios en actions.json se aplican al momento.
        actions, warnings = load_actions()

        self._prev_hwnd = get_foreground_window()

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

        tb.Label(hdr, text="⚡", font=(UI_FONT, 13), bootstyle="info").pack(side=LEFT)
        tb.Label(hdr, text=f" {APP_NAME}",
                 font=(UI_FONT, 11, "bold"), bootstyle="info").pack(side=LEFT)

        word_count = len(selected_text.split())
        char_count = len(selected_text.strip())
        tb.Label(hdr, text=f"  {word_count} pal. · {char_count} car.",
                 font=(UI_FONT, 8), bootstyle="secondary").pack(side=LEFT)

        tb.Button(hdr, text="✕", bootstyle="secondary-link",
                  command=self.hide, width=2).pack(side=RIGHT)

        tb.Separator(inner, bootstyle="info").pack(fill=X, pady=(4, 8))

        # ── Preview ────────────────────────────────────────────────────
        preview = selected_text[:80] + ("…" if len(selected_text) > 80 else "")
        prev_frame = tb.Frame(inner, padding=(8, 5))
        prev_frame.pack(fill=X, pady=(0, 10))
        tb.Label(prev_frame, text=f'"{preview}"',
                 font=(UI_FONT, 9, "italic"),
                 bootstyle="secondary", wraplength=305).pack(fill=X)

        # ── Acciones: la primera sección sin encabezado, el resto agrupadas ──
        for index, (sec_name, sec_actions) in enumerate(group_by_section(actions)):
            if index > 0:
                tb.Separator(inner, bootstyle="secondary").pack(fill=X, pady=(8, 5))
                sec_hdr = tb.Frame(inner)
                sec_hdr.pack(fill=X, pady=(0, 4))
                tb.Label(sec_hdr, text="</>",
                         font=(MONO_FONT, 8, "bold"), bootstyle="secondary").pack(side=LEFT)
                tb.Label(sec_hdr, text=f"  {sec_name.upper()}",
                         font=(UI_FONT, 8, "bold"), bootstyle="secondary").pack(side=LEFT)
            self._add_action_grid(inner, sec_actions, selected_text, ipady=5 if index == 0 else 4)

        # ── Prompt personalizado ───────────────────────────────────────
        tb.Separator(inner, bootstyle="secondary").pack(fill=X, pady=(8, 5))
        tb.Button(inner, text=f"✏️  Crear prompt personalizado   ·  {CUSTOM_PROMPT_SHORTCUT[0]}",
                  bootstyle="primary",
                  command=lambda: self._on_custom_prompt(selected_text)
                  ).pack(fill=X, pady=(0, 2), ipady=6)

        # ── Atajos de teclado ──────────────────────────────────────────
        for action in actions:
            if action.get("shortcut_key"):
                win.bind(action["shortcut_key"],
                         lambda e, a=action: self._on_action(a, selected_text))
        win.bind(CUSTOM_PROMPT_SHORTCUT[1], lambda e: self._on_custom_prompt(selected_text))

        win.update_idletasks()
        w, h   = win.winfo_reqwidth(), win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        fade_window(win, 0.97, 0.15)
        win.bind("<Escape>", lambda e: self.hide())
        win.bind("<FocusOut>", lambda e: win.after(220, self._check_focus))
        bring_app_to_front()  # macOS: activar Escriba para recibir el teclado
        win.focus_force()

        if warnings:
            self.app.tooltip.show("⚠️ actions.json:\n" + "\n".join(warnings[:4]), "warning", 7000)

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
        start_ai_action(self.app, action["prompt"], text, self._prev_hwnd, action["label"])

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
        apply_dark_style(win)
        self.window = win
        center_window(win, 520, 340)

        frame = tk.Frame(win, bg=_FM_BG, padx=16, pady=12)
        frame.pack(fill=BOTH, expand=True)

        tk.Label(frame, text="✦  Escribe tu prompt",
                 font=(UI_FONT, 12, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(anchor=W, pady=(0, 4))

        preview = selected_text[:75] + ("…" if len(selected_text) > 75 else "")
        tk.Label(frame, text=f'Texto seleccionado: "{preview}"',
                 font=(UI_FONT, 9, "italic"),
                 bg=_FM_BG, fg=_FM_MUTED, wraplength=480).pack(anchor=W, pady=(0, 8))

        tk.Frame(frame, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 8))

        btn_frame = tk.Frame(frame, bg=_FM_BG)
        btn_frame.pack(side=BOTTOM, fill=X, pady=(8, 0))
        tb.Button(btn_frame, text=f"🚀  Ejecutar  ({RUN_PROMPT_SHORTCUT[0]})",
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
            font=(UI_FONT, 10),
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

        win.bind(RUN_PROMPT_SHORTCUT[1], lambda e: self._execute())
        win.bind("<Escape>", lambda e: win.destroy())

    def _execute(self):
        custom_prompt = self.prompt_widget.get("1.0", tk.END).strip()
        if not custom_prompt:
            self.app.tooltip.show("⚠️ El prompt no puede estar vacío.", "warning")
            return
        self.window.destroy()
        start_ai_action(self.app, custom_prompt, self.selected_text, self.prev_hwnd, CUSTOM_PROMPT_LABEL)
