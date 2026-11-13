"""
Escriba — Menú flotante tipo paleta de comandos.

- Aparece junto al cursor.
- Se escribe para filtrar acciones (sin importar acentos ni mayúsculas).
- ↑/↓ para moverse, Enter para ejecutar, Esc para cerrar.
- Si lo escrito no coincide con una acción (o se elige la última fila), se usa
  como instrucción personalizada. Shift+Enter añade un salto de línea.
- Los atajos de cada acción (Ctrl+R… / ⌘R…) siguen funcionando.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from ttkbootstrap.constants import *

from actions import action_icon, action_name, display_shortcut, filter_actions, load_actions
from ai_clients import is_ready
from constants import APP_NAME
from plataforma import bring_app_to_front, get_foreground_window
from ui_common import (
    _FM_ACCENT, _FM_BADGE, _FM_BG, _FM_BORDER, _FM_CARD, _FM_HOVER, _FM_MUTED, _FM_SEP, _FM_TEXT,
    MONO_FONT, UI_FONT, fade_window, place_near_pointer, scaled,
)
from ui_result import CUSTOM_PROMPT_LABEL, start_ai_action

if TYPE_CHECKING:
    from escriba import EscribaApp

PLACEHOLDER = "Busca una acción o escribe tu propia instrucción"
MAX_ROWS = 12
MAX_INPUT_LINES = 4


def group_by_section(actions: list[dict]) -> list[tuple[str, list[dict]]]:
    """Agrupa las acciones por sección conservando el orden de aparición."""
    groups: dict[str, list[dict]] = {}
    for action in actions:
        groups.setdefault(action.get("section", ""), []).append(action)
    return list(groups.items())


def button_text(action: dict) -> str:
    """Etiqueta con atajo (se conserva para compatibilidad y pruebas)."""
    shortcut = display_shortcut(action["shortcut"]) if action.get("shortcut_key") else ""
    return f"{action['label']}   ·  {shortcut}" if shortcut else action["label"]


def build_items(actions: list[dict], query: str) -> list[dict]:
    """Filas a mostrar: acciones filtradas y, si hay texto, la instrucción libre al final."""
    items = [{"kind": "action", "action": a} for a in filter_actions(actions, query)]
    if query.strip():
        items.append({"kind": "custom", "prompt": query.strip()})
    return items


def _truncate(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


# ─────────────────────────────────────────────────────────────
# Menú Flotante de IA
# ─────────────────────────────────────────────────────────────
class FloatingMenu:
    """Paleta de comandos con las acciones de IA sobre el texto seleccionado."""

    def __init__(self, app: EscribaApp):
        self.app = app
        self.window = None
        self._prev_hwnd = None
        self._text = ""
        self._actions: list[dict] = []
        self._items: list[dict] = []
        self._rows: list[list[tk.Widget]] = []
        self._sel = 0
        self._query = ""

    # ── Apertura ────────────────────────────────────────────
    def show(self, selected_text: str):
        self.hide()
        if not selected_text.strip():
            self.app.tooltip.show(
                "No se detectó texto seleccionado. Selecciona texto y vuelve a usar el atajo.",
                "warning",
            )
            return
        if not is_ready():
            self.app.tooltip.show(
                "Configura un proveedor de IA antes de usar Escriba.",
                "warning", duration=None,
                action=("Abrir configuración", self.app.open_config),
            )
            return

        # Se leen en cada apertura: los cambios en actions.json se aplican al momento.
        self._actions, warnings = load_actions()
        self._text = selected_text
        self._query = ""
        self._sel = 0
        self._prev_hwnd = get_foreground_window()

        win = tk.Toplevel(self.app.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        win.configure(bg=_FM_BORDER)
        self.window = win

        inner = tk.Frame(win, bg=_FM_BG, padx=12, pady=10)
        inner.pack(fill=BOTH, expand=True, padx=1, pady=1)

        # ── Encabezado ──────────────────────────────────────
        hdr = tk.Frame(inner, bg=_FM_BG)
        hdr.pack(fill=X, pady=(0, 8))
        tk.Label(hdr, text="⚡", font=(UI_FONT, 11), bg=_FM_BG, fg=_FM_ACCENT).pack(side=LEFT)
        tk.Label(hdr, text=f" {APP_NAME}", font=(UI_FONT, 10, "bold"),
                 bg=_FM_BG, fg=_FM_TEXT).pack(side=LEFT)
        words = len(selected_text.split())
        tk.Label(hdr, text=f"  ·  {words} palabra{'s' if words != 1 else ''}",
                 font=(UI_FONT, 9), bg=_FM_BG, fg=_FM_MUTED).pack(side=LEFT)
        close = tk.Label(hdr, text="✕", font=(UI_FONT, 10), bg=_FM_BG, fg=_FM_MUTED, cursor="hand2")
        close.pack(side=RIGHT)
        close.bind("<Button-1>", lambda e: self.hide())

        # ── Vista previa del texto ──────────────────────────
        prev = tk.Frame(inner, bg=_FM_BG)
        prev.pack(fill=X, pady=(0, 10))
        tk.Frame(prev, bg=_FM_ACCENT, width=2).pack(side=LEFT, fill=Y)
        tk.Label(prev, text=f"“{_truncate(selected_text, 90)}”", font=(UI_FONT, 9, "italic"),
                 bg=_FM_BG, fg=_FM_MUTED, wraplength=scaled(win, 340), justify=LEFT
                 ).pack(side=LEFT, padx=(8, 0))

        # ── Buscador / instrucción libre ────────────────────
        box = tk.Frame(inner, bg=_FM_CARD, highlightthickness=1,
                       highlightbackground=_FM_ACCENT, highlightcolor=_FM_ACCENT)
        box.pack(fill=X)
        self.input = tk.Text(box, height=1, width=46, wrap=tk.WORD, font=(UI_FONT, 10),
                             bg=_FM_CARD, fg=_FM_TEXT, insertbackground=_FM_ACCENT,
                             relief="flat", borderwidth=0, padx=8, pady=6, undo=True)
        self.input.pack(fill=X)
        self._placeholder = tk.Label(box, text=PLACEHOLDER, font=(UI_FONT, 10),
                                     bg=_FM_CARD, fg=_FM_MUTED, bd=0, padx=0, pady=0)
        self._placeholder.place(x=scaled(win, 10), rely=0.5, anchor=W)
        self._placeholder.bind("<Button-1>", lambda e: self.input.focus_set())

        # ── Lista de acciones ───────────────────────────────
        self.list_frame = tk.Frame(inner, bg=_FM_BG)
        self.list_frame.pack(fill=X, pady=(6, 0))

        # ── Pie con ayudas de teclado ───────────────────────
        tk.Frame(inner, bg=_FM_SEP, height=1).pack(fill=X, pady=(8, 6))
        tk.Label(inner, text="↑↓ navegar   ·   Enter ejecutar   ·   Shift+Enter nueva línea   ·   Esc cerrar",
                 font=(UI_FONT, 8), bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W)

        self._bind_keys(win)
        self._items = build_items(self._actions, "")
        self._render()

        place_near_pointer(win)
        fade_window(win, 0.98, 0.18)
        win.bind("<FocusOut>", lambda e: win.after(220, self._check_focus))
        bring_app_to_front()  # macOS: activar Escriba para recibir el teclado
        win.focus_force()
        self.input.focus_set()

        if warnings:
            self.app.tooltip.show("actions.json tiene avisos:\n" + "\n".join(warnings[:4]),
                                  "warning", 8000)

    # ── Teclado ─────────────────────────────────────────────
    def _bind_keys(self, win):
        def stop(handler):
            def wrapper(event):
                handler()
                return "break"  # evita el comportamiento por defecto del campo de texto
            return wrapper

        self.input.bind("<Up>", stop(lambda: self._move(-1)))
        self.input.bind("<Down>", stop(lambda: self._move(1)))
        self.input.bind("<Return>", stop(self._run_selected))
        self.input.bind("<KP_Enter>", stop(self._run_selected))
        self.input.bind("<Shift-Return>", stop(self._newline))
        self.input.bind("<Escape>", stop(self.hide))
        self.input.bind("<KeyRelease>", lambda e: self._on_query_change())
        win.bind("<Escape>", lambda e: self.hide())

        for action in self._actions:
            key = action.get("shortcut_key")
            if key:
                handler = stop(lambda a=action: self._on_action(a))
                self.input.bind(key, handler)
                win.bind(key, handler)
                # Soportar Bloq Mayús activado para atajos de una letra (ej. <Control-r> -> <Control-R>).
                if len(key) >= 4 and key[-2].isalpha() and key[-2].islower() and key[-3] == "-":
                    upper_key = key[:-2] + key[-2].upper() + ">"
                    self.input.bind(upper_key, handler)
                    win.bind(upper_key, handler)

    def _newline(self):
        self.input.insert(tk.INSERT, "\n")
        self._on_query_change()

    def _on_query_change(self):
        if not self.window or not self.window.winfo_exists():
            return
        query = self.input.get("1.0", "end-1c")
        try:
            lines = int(self.input.count("1.0", "end", "displaylines")[0])
        except Exception:
            lines = query.count("\n") + 1
        self.input.configure(height=max(1, min(MAX_INPUT_LINES, lines)))
        if query.strip():
            self._placeholder.place_forget()
        else:
            self._placeholder.place(x=scaled(self.window, 10), rely=0.5, anchor=W)
        if query != self._query:
            self._query = query
            self._items = build_items(self._actions, query)
            self._sel = 0
            self._render()

    # ── Lista ───────────────────────────────────────────────
    def _render(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._rows = []

        grouped = not self._query.strip()
        last_section = None
        for index, item in enumerate(self._items[:MAX_ROWS]):
            if grouped and item["kind"] == "action":
                section = item["action"].get("section", "")
                if section != last_section:
                    tk.Label(self.list_frame, text=section, font=(UI_FONT, 8, "bold"),
                             bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W, padx=6, pady=(5, 1))
                    last_section = section
            self._rows.append(self._make_row(index, item))

        hidden = len(self._items) - MAX_ROWS
        if hidden > 0:
            tk.Label(self.list_frame, text=f"y {hidden} más: escribe para filtrar",
                     font=(UI_FONT, 8), bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W, padx=6, pady=(4, 0))
        self._highlight()
        if self.window:
            self.window.update_idletasks()

    def _make_row(self, index: int, item: dict) -> list[tk.Widget]:
        row = tk.Frame(self.list_frame, bg=_FM_BG, cursor="hand2", padx=6, pady=3)
        row.pack(fill=X)
        if item["kind"] == "action":
            action = item["action"]
            icon, text = action_icon(action), action_name(action)
            key = display_shortcut(action["shortcut"]) if action.get("shortcut_key") else ""
        else:
            icon, text, key = "✏", f"Usar como instrucción: “{_truncate(item['prompt'], 38)}”", "Enter"

        icon_lbl = tk.Label(row, text=icon, width=2, font=(UI_FONT, 11), bg=_FM_BG, fg=_FM_ACCENT)
        icon_lbl.pack(side=LEFT)
        text_lbl = tk.Label(row, text=text, font=(UI_FONT, 10), bg=_FM_BG, fg=_FM_TEXT, anchor=W)
        text_lbl.pack(side=LEFT, fill=X, expand=True, padx=(6, 0))
        widgets: list[tk.Widget] = [row, icon_lbl, text_lbl]
        if key:
            badge = tk.Label(row, text=key, font=(MONO_FONT, 8), bg=_FM_BADGE, fg=_FM_MUTED,
                             padx=6, pady=1, highlightthickness=1, highlightbackground=_FM_BORDER)
            badge.pack(side=RIGHT)
            widgets.append(badge)

        for w in widgets:
            w.bind("<Button-1>", lambda e, i=index: self._run_index(i))
            w.bind("<Enter>", lambda e, i=index: self._set_selection(i))
        return widgets

    def _highlight(self):
        for i, widgets in enumerate(self._rows):
            bg = _FM_HOVER if i == self._sel else _FM_BG
            for w in widgets[:3]:  # la insignia del atajo conserva su fondo
                w.configure(bg=bg)

    def _set_selection(self, index: int):
        if 0 <= index < len(self._rows):
            self._sel = index
            self._highlight()

    def _move(self, delta: int):
        if self._rows:
            self._set_selection((self._sel + delta) % len(self._rows))

    def _run_selected(self):
        self._run_index(self._sel)

    def _run_index(self, index: int):
        if not (0 <= index < len(self._items)):
            return
        item = self._items[index]
        if item["kind"] == "action":
            self._on_action(item["action"])
        else:
            self._on_custom_prompt(item["prompt"])

    # ── Cierre y ejecución ──────────────────────────────────
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

    def _on_action(self, action: dict):
        self.hide()
        start_ai_action(self.app, action["prompt"], self._text, self._prev_hwnd, action["label"])

    def _on_custom_prompt(self, prompt: str):
        self.hide()
        start_ai_action(self.app, prompt, self._text, self._prev_hwnd, CUSTOM_PROMPT_LABEL)
