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

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from actions import (
    action_icon, action_matches_app, action_name, add_custom_action, display_shortcut,
    expand_prompt_vars, extract_prompt_inputs, filter_actions, is_translation_action, load_actions,
)
from ai_clients import is_ready
from config import ConfigManager, tr
from constants import APP_NAME
from plataforma import bring_app_to_front, get_foreground_app_name, get_foreground_window, tk_shortcut
from ui_common import (
    _FM_ACCENT, _FM_BADGE, _FM_BG, _FM_BORDER, _FM_CARD, _FM_HOVER, _FM_MUTED, _FM_SEP, _FM_TEXT,
    MONO_FONT, UI_FONT, apply_dark_style, center_window, fade_window, place_near_pointer, scaled,
)
from ui_result import start_ai_action

if TYPE_CHECKING:
    from escriba import EscribaApp

PLACEHOLDER = "Busca una acción o escribe tu propia instrucción"
PLACEHOLDER_COMPOSE = "Escribe qué quieres generar o redactar…"
MAX_LIST_HEIGHT = 340
MAX_INPUT_LINES = 4
LONG_TEXT_CHARS = 10000
MAX_RECENT_PROMPTS = 8


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


def _mode_matches(action: dict, has_selection: bool) -> bool:
    mode = action.get("mode", "selection") or "selection"
    if has_selection:
        return mode in ("selection", "both")
    return mode in ("compose", "both")


def build_items(
    actions: list[dict],
    query: str,
    has_selection: bool = True,
    app_name: str = "",
    recent_prompts: list[str] | None = None,
) -> list[dict]:
    """Filas a mostrar: acciones filtradas, recientes opcionales e instrucción libre."""
    eligible = [
        a for a in actions
        if _mode_matches(a, has_selection) and action_matches_app(a, app_name)
    ]
    if app_name and not query.strip():
        app_specific = [a for a in eligible if a.get("apps")]
        if app_specific:
            promoted = [{**a, "section": tr("menu.section_for_app", app=app_name)} for a in app_specific]
            app_labels = {a["label"] for a in app_specific}
            eligible = promoted + [a for a in eligible if a["label"] not in app_labels]

    items = [{"kind": "action", "action": a} for a in filter_actions(eligible, query)]
    if not query.strip() and recent_prompts:
        for p in recent_prompts[:3]:
            if p and p.strip():
                items.append({"kind": "recent", "prompt": p.strip()})
    if query.strip():
        items.append({"kind": "custom", "prompt": query.strip()})
    return items


def _with_frequent_first(actions: list[dict]) -> list[dict]:
    """Coloca arriba hasta 2 acciones muy usadas (uso >= 2) sin duplicarlas."""
    usage = ConfigManager.get("action_usage", {}) or {}
    if not isinstance(usage, dict):
        return actions
    ranked = sorted(
        (a for a in actions if usage.get(a["label"], 0) >= 2),
        key=lambda a: usage.get(a["label"], 0),
        reverse=True,
    )[:2]
    if not ranked:
        return actions
    top_labels = {a["label"] for a in ranked}
    promoted = [{**a, "section": tr("menu.section_frequent")} for a in ranked]
    rest = [a for a in actions if a["label"] not in top_labels]
    return promoted + rest


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
        self._app_name = ""
        self._text = ""
        self._has_selection = True
        self._actions: list[dict] = []
        self._items: list[dict] = []
        self._rows: list[list[tk.Widget]] = []
        self._sel = 0
        self._query = ""
        self._canvas = None
        self._inner_list = None
        self._canvas_win = None
        self._vscroll = None

    @staticmethod
    def _recent_prompts() -> list[str]:
        try:
            raw = ConfigManager.get("recent_prompts", []) or []
            return [str(p).strip() for p in raw if isinstance(p, str) and p.strip()][:MAX_RECENT_PROMPTS]
        except Exception:
            return []

    @classmethod
    def _record_recent_prompt(cls, prompt: str):
        clean = (prompt or "").strip()
        if not clean:
            return
        try:
            cur = [p for p in cls._recent_prompts() if p != clean]
            ConfigManager.set("recent_prompts", ([clean] + cur)[:MAX_RECENT_PROMPTS])
        except Exception:
            pass

    # ── Apertura ────────────────────────────────────────────
    def show(self, selected_text: str):
        self.hide()
        if not is_ready():
            self.app.tooltip.show(
                tr("menu.not_configured"),
                "warning", duration=None,
                action=(tr("menu.open_config"), self.app.open_config),
            )
            return

        # Se leen en cada apertura: los cambios en actions.json se aplican al momento.
        actions, warnings = load_actions()
        self._actions = _with_frequent_first(actions)
        self._text = selected_text
        self._has_selection = bool(selected_text.strip())
        self._query = ""
        self._sel = 0
        self._prev_hwnd = get_foreground_window()
        self._app_name = get_foreground_app_name(self._prev_hwnd)

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
        if self._has_selection:
            words = len(selected_text.split())
            word_lbl = tr("menu.word_singular") if words == 1 else tr("menu.word_plural")
            tk.Label(hdr, text=f"  ·  {words} {word_lbl}",
                     font=(UI_FONT, 9), bg=_FM_BG, fg=_FM_MUTED).pack(side=LEFT)
            if len(selected_text) > LONG_TEXT_CHARS:
                tk.Label(hdr, text=tr("menu.long_text"),
                         font=(UI_FONT, 8, "bold"), bg=_FM_BG, fg=_FM_ACCENT).pack(side=LEFT)
        else:
            tk.Label(hdr, text=tr("menu.compose_mode"),
                     font=(UI_FONT, 9), bg=_FM_BG, fg=_FM_ACCENT).pack(side=LEFT)
        if self._app_name:
            tk.Label(hdr, text=f"  ·  {self._app_name}",
                     font=(UI_FONT, 8), bg=_FM_BG, fg=_FM_MUTED).pack(side=LEFT)
        close = tk.Label(hdr, text="✕", font=(UI_FONT, 10), bg=_FM_BG, fg=_FM_MUTED, cursor="hand2")
        close.pack(side=RIGHT)
        close.bind("<Button-1>", lambda e: self.hide())

        # ── Vista previa del texto ──────────────────────────
        if self._has_selection:
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
        ph_text = tr("menu.placeholder") if self._has_selection else tr("menu.placeholder_compose")
        self._placeholder = tk.Label(box, text=ph_text, font=(UI_FONT, 10),
                                     bg=_FM_CARD, fg=_FM_MUTED, bd=0, padx=0, pady=0)
        self._placeholder.place(x=scaled(win, 10), rely=0.5, anchor=W)
        self._placeholder.bind("<Button-1>", lambda e: self.input.focus_set())

        # ── Lista de acciones con scroll ────────────────────
        self.list_frame = tk.Frame(inner, bg=_FM_BG)
        self.list_frame.pack(fill=X, pady=(6, 0))
        self._canvas = tk.Canvas(self.list_frame, bg=_FM_BG, highlightthickness=0, bd=0, height=0)
        self._vscroll = tb.Scrollbar(self.list_frame, orient="vertical",
                                     command=self._canvas.yview, style="Escriba.Vertical.TScrollbar")
        self._canvas.configure(yscrollcommand=self._vscroll.set)
        self._inner_list = tk.Frame(self._canvas, bg=_FM_BG)
        self._canvas_win = self._canvas.create_window((0, 0), window=self._inner_list, anchor="nw")
        self._canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self._inner_list.bind(
            "<Configure>",
            lambda e: self._sync_scroll_region(),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfigure(self._canvas_win, width=e.width),
        )
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._canvas.bind(seq, self._on_mousewheel)
            self._inner_list.bind(seq, self._on_mousewheel)

        # ── Pie con ayudas de teclado ───────────────────────
        tk.Frame(inner, bg=_FM_SEP, height=1).pack(fill=X, pady=(8, 6))
        tk.Label(inner, text=tr("menu.footer"),
                 font=(UI_FONT, 8), bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W)

        self._bind_keys(win)
        self._items = build_items(
            self._actions, "", has_selection=self._has_selection,
            app_name=self._app_name, recent_prompts=self._recent_prompts(),
        )
        self._render()

        place_near_pointer(win)
        fade_window(win, 0.98, 0.18)
        win.bind("<FocusOut>", lambda e: win.after(220, self._check_focus))
        bring_app_to_front()  # macOS: activar Escriba para recibir el teclado
        win.focus_force()
        self.input.focus_set()

        if warnings:
            self.app.tooltip.show(tr("menu.warnings", warnings="\n".join(warnings[:4])),
                                  "warning", 8000)

    def _on_mousewheel(self, event):
        if self._canvas and self._vscroll.winfo_ismapped():
            if getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            else:
                delta = -1 if event.delta > 0 else 1
            self._canvas.yview_scroll(delta, "units")

    def _sync_scroll_region(self):
        if not self._canvas or not self._inner_list or not self.window or not self.window.winfo_exists():
            return
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        req_h = self._inner_list.winfo_reqheight()
        max_h = scaled(self.window, MAX_LIST_HEIGHT)
        self._canvas.configure(height=min(req_h, max_h))
        if req_h > max_h:
            if not self._vscroll.winfo_ismapped():
                self._vscroll.pack(side=RIGHT, fill=Y)
        else:
            if self._vscroll.winfo_ismapped():
                self._vscroll.pack_forget()

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
        self.input.bind(tk_shortcut("s"), stop(lambda: self._save_custom_prompt(self.input.get("1.0", "end-1c"))))
        self.input.bind("<KeyRelease>", lambda e: self._on_query_change())
        win.bind("<Escape>", lambda e: self.hide())

        for action in self._actions:
            if not (_mode_matches(action, self._has_selection) and action_matches_app(action, self._app_name)):
                continue
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
            self._items = build_items(
                self._actions, query, has_selection=self._has_selection,
                app_name=self._app_name, recent_prompts=self._recent_prompts(),
            )
            self._sel = 0
            self._render()

    # ── Lista ───────────────────────────────────────────────
    def _render(self):
        container = self._inner_list
        for child in container.winfo_children():
            child.destroy()
        self._rows = []

        grouped = not self._query.strip()
        last_section = None
        for index, item in enumerate(self._items):
            if grouped:
                if item["kind"] == "action":
                    section = item["action"].get("section", "")
                elif item["kind"] == "recent":
                    section = tr("menu.section_recent")
                else:
                    section = None
                if section and section != last_section:
                    tk.Label(container, text=section, font=(UI_FONT, 8, "bold"),
                             bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W, padx=6, pady=(5, 1))
                    last_section = section
            self._rows.append(self._make_row(index, item))

        self._highlight()
        if self.window:
            self.window.update_idletasks()
            self._sync_scroll_region()

    def _make_row(self, index: int, item: dict) -> list[tk.Widget]:
        row = tk.Frame(self._inner_list, bg=_FM_BG, cursor="hand2", padx=6, pady=3)
        row.pack(fill=X)
        kind = item["kind"]
        if kind == "action":
            action = item["action"]
            icon, text = action_icon(action), action_name(action)
            key = display_shortcut(action["shortcut"]) if action.get("shortcut_key") else ""
        elif kind == "recent":
            icon, text, key = "🕘", _truncate(item["prompt"], 42), "Enter"
        else:
            verb = tr("menu.verb_use") if self._has_selection else tr("menu.verb_generate")
            icon, text, key = "✏", f"{verb}: “{_truncate(item['prompt'], 34)}”", "Enter"

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
        if kind in ("custom", "recent"):
            save_lbl = tk.Label(
                row, text=tr("menu.save_badge"), font=(UI_FONT, 8), bg=_FM_BADGE, fg=_FM_ACCENT,
                padx=6, pady=1, cursor="hand2",
            )
            save_lbl.pack(side=RIGHT, padx=(0, 4))
            save_lbl.bind("<Button-1>", lambda e, p=item["prompt"]: self._save_custom_prompt(p))

        for w in widgets:
            w.bind("<Button-1>", lambda e, i=index: self._run_index(i))
            w.bind("<Enter>", lambda e, i=index: self._set_selection(i))
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                w.bind(seq, self._on_mousewheel)
        return widgets

    def _save_custom_prompt(self, prompt: str):
        clean = (prompt or "").strip()
        if not clean:
            return
        try:
            label = _truncate(clean, 26)
            add_custom_action(label, clean, mode="both")
            actions, _ = load_actions()
            self._actions = _with_frequent_first(actions)
            self._items = build_items(
                self._actions, self._query, has_selection=self._has_selection,
                app_name=self._app_name, recent_prompts=self._recent_prompts(),
            )
            if self.window and self.window.winfo_exists():
                self._render()
            self.app.tooltip.show(tr("menu.saved_ok", label=label), "success", 2500)
        except Exception as exc:
            self.app.tooltip.show(tr("menu.saved_err", error=exc), "danger", 4000)

    def _highlight(self):
        for i, widgets in enumerate(self._rows):
            bg = _FM_HOVER if i == self._sel else _FM_BG
            for w in widgets[:3]:  # la insignia del atajo conserva su fondo
                w.configure(bg=bg)

    def _ensure_visible(self, index: int):
        if not self._canvas or not self._rows or not (0 <= index < len(self._rows)):
            return
        total_h = self._inner_list.winfo_reqheight()
        if total_h <= 0:
            return
        row = self._rows[index][0]
        y0 = row.winfo_y()
        y1 = y0 + row.winfo_height()
        top_frac, bot_frac = self._canvas.yview()
        view_h = total_h
        if y0 < top_frac * view_h:
            self._canvas.yview_moveto(y0 / view_h)
        elif y1 > bot_frac * view_h:
            vis_h = (bot_frac - top_frac) * view_h
            self._canvas.yview_moveto(max(0.0, (y1 - vis_h) / view_h))

    def _set_selection(self, index: int):
        if 0 <= index < len(self._rows):
            self._sel = index
            self._highlight()

    def _move(self, delta: int):
        if self._rows:
            new_idx = (self._sel + delta) % len(self._rows)
            self._set_selection(new_idx)
            self._ensure_visible(new_idx)

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

    @staticmethod
    def _record_usage(label: str):
        try:
            usage = ConfigManager.get("action_usage", {}) or {}
            if not isinstance(usage, dict):
                usage = {}
            usage[label] = int(usage.get(label, 0)) + 1
            ConfigManager.set("action_usage", usage)
        except Exception:
            pass

    def _ask_prompt_inputs(self, title: str, fields: list[str]) -> dict[str, str] | None:
        """Diálogo modal compacto para rellenar variables `{input:Etiqueta}`."""
        result: dict[str, str] | None = None
        dlg = tb.Toplevel(self.app.root)
        dlg.title(f"{APP_NAME} — {title}")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        apply_dark_style(dlg)
        center_window(dlg, 380, 120 + len(fields) * 56)

        frame = tk.Frame(dlg, bg=_FM_BG, padx=18, pady=14)
        frame.pack(fill=BOTH, expand=True)

        vars_map: dict[str, tk.StringVar] = {}
        first_entry = None
        for name in fields:
            tk.Label(frame, text=name, font=(UI_FONT, 9, "bold"),
                     bg=_FM_BG, fg=_FM_TEXT).pack(anchor=W, pady=(0, 3))
            var = tk.StringVar()
            entry = tb.Entry(frame, textvariable=var, font=(UI_FONT, 10), style="Escriba.TEntry")
            entry.pack(fill=X, ipady=3, pady=(0, 8))
            vars_map[name] = var
            if first_entry is None:
                first_entry = entry

        btns = tk.Frame(frame, bg=_FM_BG)
        btns.pack(fill=X, pady=(4, 0))

        def _submit(event=None):
            nonlocal result
            result = {k: v.get().strip() for k, v in vars_map.items()}
            dlg.destroy()

        tb.Button(btns, text=tr("common.cancel"), style="Escriba.TButton",
                  command=dlg.destroy).pack(side=LEFT)
        tb.Button(btns, text=tr("menu.run"), bootstyle="warning",
                  command=_submit).pack(side=RIGHT)
        dlg.bind("<Return>", _submit)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.grab_set()
        if first_entry:
            first_entry.focus_set()
        dlg.wait_window()
        return result

    def _on_action(self, action: dict):
        self.hide()
        inputs = extract_prompt_inputs(action["prompt"])
        extra = None
        if inputs:
            extra = self._ask_prompt_inputs(action_name(action), inputs)
            if extra is None:
                return
        self._record_usage(action["label"])
        all_vars = {"app": self._app_name, **(extra or {})}
        prompt = expand_prompt_vars(action["prompt"], extra_vars=all_vars)
        apply_language = not is_translation_action(action)
        kwargs = {"apply_language": apply_language}
        if action.get("model"):
            kwargs["model"] = action["model"]
        if action.get("temperature") is not None:
            kwargs["temperature"] = action["temperature"]
        if action.get("strip_markdown"):
            kwargs["strip_markdown"] = True
        if hasattr(self.app, "remember_last_action"):
            self.app.remember_last_action(
                prompt=action["prompt"],
                label=action["label"],
                auto_replace=bool(action.get("auto_replace")),
                **kwargs,
            )
        start_ai_action(
            self.app, prompt, self._text, self._prev_hwnd, action["label"],
            auto_replace=bool(action.get("auto_replace")),
            **kwargs,
        )

    def _on_custom_prompt(self, prompt: str):
        self.hide()
        self._record_recent_prompt(prompt)
        inputs = extract_prompt_inputs(prompt)
        extra = None
        if inputs:
            extra = self._ask_prompt_inputs(tr("menu.free_instruction"), inputs)
            if extra is None:
                return
        all_vars = {"app": self._app_name, **(extra or {})}
        expanded = expand_prompt_vars(prompt, extra_vars=all_vars)
        apply_language = not is_translation_action(expanded)
        custom_label = tr("result.custom_prompt")
        if hasattr(self.app, "remember_last_action"):
            self.app.remember_last_action(
                prompt=prompt, label=custom_label, apply_language=apply_language
            )
        start_ai_action(
            self.app, expanded, self._text, self._prev_hwnd, custom_label,
            apply_language=apply_language,
        )
