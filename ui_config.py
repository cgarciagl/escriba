"""
Escriba — Ventana de Configuración (pestañas Gemini / Alternativo / General).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from actions import load_actions, save_actions, write_defaults
from ai_clients import GeminiClient, OpenAICompatibleClient
from config import ConfigManager
from constants import (
    APP_NAME,
    DEFAULT_HOTKEY,
    GEMINI_DEFAULT_MODEL,
    GEMINI_FALLBACK_MODELS,
    HOTKEY_PRESETS,
    OPENAI_DEFAULT_BASE_URL,
    OPENAI_DEFAULT_MODEL,
)
from plataforma import HOTKEY_LABEL, IS_MAC, StartupManager
from ui_common import (
    _FM_ACCENT, _FM_BG, _FM_BORDER, _FM_CARD, _FM_MUTED, _FM_SEP, _FM_TEXT, MONO_FONT, UI_FONT,
    apply_dark_style, center_window,
)

if TYPE_CHECKING:
    from escriba import EscribaApp

_WARN = "#f59e0b"


def open_in_editor(path: str):
    """Abre un archivo con la aplicación predeterminada del sistema."""
    if hasattr(os, "startfile"):
        os.startfile(path)  # Windows
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class ConfigWindow:
    """Formulario de proveedores de IA, acciones, streaming y arranque."""

    WIDTH, HEIGHT = 540, 600

    def __init__(self, app: EscribaApp):
        self.app = app
        self.window = None

    # ── Helpers de maquetación ──────────────────────────────
    @staticmethod
    def _title(parent, text: str, pady=(0, 6)):
        tk.Label(parent, text=text, font=(UI_FONT, 10, "bold"),
                 bg=_FM_BG, fg=_FM_TEXT).pack(anchor=W, pady=pady)

    @staticmethod
    def _hint(parent, text: str, pady=(0, 14)) -> tk.Label:
        lbl = tk.Label(parent, text=text, font=(UI_FONT, 8), bg=_FM_BG,
                       fg=_FM_MUTED, wraplength=450, justify=LEFT)
        lbl.pack(anchor=W, pady=pady)
        return lbl

    @staticmethod
    def _tab(notebook, text: str) -> tk.Frame:
        tab = tk.Frame(notebook, bg=_FM_BG, padx=20, pady=16)
        notebook.add(tab, text=f"  {text}  ")
        return tab

    # ── Construcción ────────────────────────────────────────
    def show(self, welcome: bool = False):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        win = tb.Toplevel(self.app.root)
        win.title(f"{APP_NAME} — Configuración")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        apply_dark_style(win)
        center_window(win, self.WIDTH, self.HEIGHT)
        self.window = win

        frame = tk.Frame(win, bg=_FM_BG, padx=20, pady=16)
        frame.pack(fill=BOTH, expand=True)

        # ── Header ──────────────────────────────────────────
        hdr = tk.Frame(frame, bg=_FM_BG)
        hdr.pack(fill=X, pady=(0, 10))
        badge = tk.Frame(hdr, bg=_FM_ACCENT, padx=10, pady=8)
        badge.pack(side=LEFT, padx=(0, 12))
        tk.Label(badge, text="⚡︎", font=(UI_FONT, 16, "bold"),
                 bg=_FM_ACCENT, fg=_FM_BG).pack()
        title_col = tk.Frame(hdr, bg=_FM_BG)
        title_col.pack(side=LEFT)
        tk.Label(title_col, text=APP_NAME,
                 font=(UI_FONT, 14, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(anchor=W)
        tk.Label(title_col, text="Configuración",
                 font=(UI_FONT, 9), bg=_FM_BG, fg=_FM_MUTED).pack(anchor=W)

        # ── Pie: estado + guardar (se empaqueta antes para que siempre se vea) ──
        footer = tk.Frame(frame, bg=_FM_BG)
        footer.pack(side=BOTTOM, fill=X, pady=(10, 0))
        self.status_var = tk.StringVar()
        self.status_lbl = tk.Label(footer, textvariable=self.status_var,
                                   font=(UI_FONT, 9), wraplength=480,
                                   bg=_FM_BG, fg=_FM_MUTED)
        self.status_lbl.pack(anchor=W, pady=(0, 8))
        tb.Button(footer, text="💾  Guardar y Cerrar", bootstyle="warning",
                  width=26, command=self._save).pack()

        notebook = tb.Notebook(frame, style="Escriba.TNotebook")
        notebook.pack(fill=BOTH, expand=True)

        self._build_gemini_tab(self._tab(notebook, "Gemini"))
        self._build_alt_tab(self._tab(notebook, "Proveedor alternativo"))
        self._build_actions_tab(self._tab(notebook, "Acciones"))
        self._build_general_tab(self._tab(notebook, "General"))

        # Indicadores ámbar sobre el fondo de Escriba (no el del tema)
        style = tb.Style()
        for name in ("warning.TCheckbutton", "warning.TRadiobutton"):
            style.configure(name, background=_FM_BG, foreground=_FM_TEXT, font=(UI_FONT, 9))
            style.map(name, background=[("active", _FM_BG)])

        self.key_entry.focus_set()
        if welcome:
            self._status(
                "👋 Te damos la bienvenida a Escriba. Pega tu API Key de Gemini (es gratuita) "
                "o configura un proveedor alternativo, y pulsa Guardar.", _FM_ACCENT)
        def _on_return(event):
            wclass = event.widget.winfo_class() if event and event.widget else ""
            if wclass not in ("TButton", "Button", "TCombobox", "Text"):
                self._save()

        win.bind("<Return>", _on_return)
        win.bind("<Escape>", lambda e: self._close())
        win.protocol("WM_DELETE_WINDOW", self._close)

        # Intentar cargar modelos en segundo plano al abrir si hay key
        if self.api_key_var.get().strip():
            threading.Thread(target=self._async_fetch_models, daemon=True).start()

    @staticmethod
    def _secret_row(parent, var: tk.StringVar, font_size: int = 11) -> tb.Entry:
        row = tk.Frame(parent, bg=_FM_BG)
        row.pack(fill=X, pady=(0, 4))
        entry = tb.Entry(row, textvariable=var, show="•",
                         font=(MONO_FONT, font_size), style="Escriba.TEntry")
        entry.pack(side=LEFT, fill=X, expand=True, ipady=4, padx=(0, 6))

        def toggle():
            showing = entry.cget("show") == ""
            entry.configure(show="•" if showing else "")
            btn.configure(text="👁" if showing else "🙈")

        btn = tb.Button(row, text="👁", style="Escriba.TButton", width=3, command=toggle)
        btn.pack(side=LEFT, ipady=2)
        return entry

    def _build_gemini_tab(self, tab):
        self._title(tab, "API Key de Google Gemini")
        self.api_key_var = tk.StringVar(value=ConfigManager.get_api_key())
        self.key_entry = self._secret_row(tab, self.api_key_var, font_size=11)

        url_label = tk.Label(tab, text="Obtén tu clave en → https://aistudio.google.com/apikey",
                             font=(UI_FONT, 9), bg=_FM_BG, fg=_FM_MUTED, cursor="hand2")
        url_label.pack(anchor=W, pady=(0, 4))
        url_label.bind("<Button-1>", lambda e: webbrowser.open("https://aistudio.google.com/apikey"))
        self._hint(tab, "Se guarda en el Llavero de macOS." if IS_MAC
                   else "Se guarda cifrada con tu cuenta de Windows (DPAPI).")

        self._title(tab, "Modelo de Gemini")
        current_model = ConfigManager.get("model", GEMINI_DEFAULT_MODEL)
        self.model_var = tk.StringVar(value=current_model)

        model_row = tk.Frame(tab, bg=_FM_BG)
        model_row.pack(fill=X, pady=(0, 4))
        initial_models = [GEMINI_DEFAULT_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_DEFAULT_MODEL]
        if current_model not in initial_models:
            initial_models.insert(0, current_model)

        self.model_cb = tb.Combobox(model_row, textvariable=self.model_var, values=initial_models,
                                    state="readonly", style="Escriba.TCombobox", font=(MONO_FONT, 10))
        self.model_cb.pack(side=LEFT, fill=X, expand=True, ipady=4, padx=(0, 8))

        self.refresh_btn = tb.Button(model_row, text="🔄 Actualizar",
                                     style="Escriba.TButton", command=self._refresh_models)
        self.refresh_btn.pack(side=LEFT, ipady=2)
        self._hint(tab, f"Predeterminado: {GEMINI_DEFAULT_MODEL} (rápido y eficiente)")

    def _build_alt_tab(self, tab):
        self._hint(tab, "Cualquier servidor compatible con la API de OpenAI: Ollama (local, sin clave), "
                        "OpenAI, OpenRouter, LM Studio…", pady=(0, 12))

        self._title(tab, "Proveedor principal")
        self.provider_var = tk.StringVar(value=ConfigManager.get("provider", "gemini"))
        prov_row = tk.Frame(tab, bg=_FM_BG)
        prov_row.pack(fill=X, pady=(0, 12))
        tb.Radiobutton(prov_row, text="Google Gemini", value="gemini",
                       variable=self.provider_var, bootstyle="warning").pack(side=LEFT, padx=(0, 18))
        tb.Radiobutton(prov_row, text="Compatible con OpenAI", value="openai",
                       variable=self.provider_var, bootstyle="warning").pack(side=LEFT)

        self._title(tab, "URL base")
        self.alt_url_var = tk.StringVar(value=ConfigManager.get("openai_base_url", OPENAI_DEFAULT_BASE_URL))
        tb.Entry(tab, textvariable=self.alt_url_var, font=(MONO_FONT, 10),
                 style="Escriba.TEntry").pack(fill=X, ipady=4, pady=(0, 10))

        self._title(tab, "API Key (opcional)")
        self.alt_key_var = tk.StringVar(value=ConfigManager.get_openai_api_key())
        self._secret_row(tab, self.alt_key_var, font_size=10)

        self._title(tab, "Modelo")
        alt_row = tk.Frame(tab, bg=_FM_BG)
        alt_row.pack(fill=X, pady=(0, 10))
        self.alt_model_var = tk.StringVar(value=ConfigManager.get("openai_model", OPENAI_DEFAULT_MODEL))
        self.alt_model_cb = tb.Combobox(alt_row, textvariable=self.alt_model_var,
                                        values=[self.alt_model_var.get()],
                                        style="Escriba.TCombobox", font=(MONO_FONT, 10))
        self.alt_model_cb.pack(side=LEFT, fill=X, expand=True, ipady=3, padx=(0, 8))
        self.alt_refresh_btn = tb.Button(alt_row, text="🔄 Listar", style="Escriba.TButton",
                                         command=self._refresh_alt_models)
        self.alt_refresh_btn.pack(side=LEFT, ipady=2)

        self.fallback_var = tk.BooleanVar(value=bool(ConfigManager.get("fallback_enabled", False)))
        tb.Checkbutton(tab, text="  Si el proveedor principal falla, usar el otro",
                       variable=self.fallback_var,
                       bootstyle="warning").pack(anchor=W, pady=(4, 0))

    def _build_actions_tab(self, tab):
        self._edited_actions, _ = load_actions()
        self._selected_action_idx = 0 if self._edited_actions else -1

        cols = tk.Frame(tab, bg=_FM_BG)
        cols.pack(fill=BOTH, expand=True)

        left = tk.Frame(cols, bg=_FM_BG, width=170)
        left.pack(side=LEFT, fill=Y, padx=(0, 12))
        left.pack_propagate(False)

        self._act_listbox = tk.Listbox(
            left, bg=_FM_CARD, fg=_FM_TEXT, selectbackground=_FM_ACCENT,
            selectforeground=_FM_BG, relief="flat", highlightthickness=1,
            highlightbackground=_FM_BORDER, font=(UI_FONT, 9), exportselection=False,
        )
        self._act_listbox.pack(fill=BOTH, expand=True, pady=(0, 6))
        self._act_listbox.bind("<<ListboxSelect>>", self._on_action_select)

        lbtns = tk.Frame(left, bg=_FM_BG)
        lbtns.pack(fill=X)
        for txt, cmd in (("+", self._act_add), ("▲", lambda: self._act_move(-1)),
                         ("▼", lambda: self._act_move(1)), ("🗑", self._act_delete)):
            tb.Button(lbtns, text=txt, style="Escriba.TButton", width=3,
                      command=cmd).pack(side=LEFT, expand=True, fill=X, padx=1)

        right = tk.Frame(cols, bg=_FM_BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        self._act_label_var = tk.StringVar()
        self._act_section_var = tk.StringVar()
        self._act_shortcut_var = tk.StringVar()
        self._act_auto_var = tk.BooleanVar()

        self._title(right, "Etiqueta (ej. ✎  Reescribir)", pady=(0, 2))
        tb.Entry(right, textvariable=self._act_label_var, font=(UI_FONT, 9),
                 style="Escriba.TEntry").pack(fill=X, pady=(0, 6))

        meta = tk.Frame(right, bg=_FM_BG)
        meta.pack(fill=X, pady=(0, 6))
        c1 = tk.Frame(meta, bg=_FM_BG)
        c1.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))
        self._title(c1, "Sección", pady=(0, 2))
        tb.Entry(c1, textvariable=self._act_section_var, font=(UI_FONT, 9),
                 style="Escriba.TEntry").pack(fill=X)
        c2 = tk.Frame(meta, bg=_FM_BG)
        c2.pack(side=LEFT, fill=X, expand=True)
        self._title(c2, "Atajo (ej. Ctrl+R)", pady=(0, 2))
        tb.Entry(c2, textvariable=self._act_shortcut_var, font=(MONO_FONT, 9),
                 style="Escriba.TEntry").pack(fill=X)

        tb.Checkbutton(right, text="  Sustituir texto automáticamente sin abrir ventana",
                       variable=self._act_auto_var, bootstyle="warning").pack(anchor=W, pady=(0, 6))

        self._title(right, "Prompt (soporta {clipboard} y {lang})", pady=(0, 2))
        self._act_prompt_txt = tk.Text(
            right, height=5, wrap=tk.WORD, font=(UI_FONT, 9),
            bg=_FM_CARD, fg=_FM_TEXT, insertbackground=_FM_ACCENT,
            relief="flat", highlightthickness=1, highlightbackground=_FM_BORDER, padx=6, pady=6,
        )
        self._act_prompt_txt.pack(fill=BOTH, expand=True, pady=(0, 8))

        tb.Button(right, text="💾  Guardar acciones", style="Escriba.TButton",
                  command=self._save_visual_actions).pack(anchor=E)

        self._refresh_actions_listbox()

    def _refresh_actions_listbox(self):
        self._act_listbox.delete(0, tk.END)
        for a in self._edited_actions:
            self._act_listbox.insert(tk.END, a["label"])
        if 0 <= self._selected_action_idx < len(self._edited_actions):
            self._act_listbox.selection_set(self._selected_action_idx)
            self._load_action_fields(self._selected_action_idx)

    def _load_action_fields(self, idx: int):
        if not (0 <= idx < len(self._edited_actions)):
            return
        a = self._edited_actions[idx]
        self._act_label_var.set(a.get("label", ""))
        self._act_section_var.set(a.get("section", ""))
        self._act_shortcut_var.set(a.get("shortcut", ""))
        self._act_auto_var.set(bool(a.get("auto_replace", False)))
        self._act_prompt_txt.delete("1.0", tk.END)
        self._act_prompt_txt.insert("1.0", a.get("prompt", ""))

    def _commit_current_action(self):
        idx = self._selected_action_idx
        if not (0 <= idx < len(self._edited_actions)):
            return
        cur = self._edited_actions[idx]
        cur["label"] = self._act_label_var.get().strip() or cur["label"]
        cur["section"] = self._act_section_var.get().strip() or "Texto y Contenido"
        cur["shortcut"] = self._act_shortcut_var.get().strip()
        cur["auto_replace"] = bool(self._act_auto_var.get())
        cur["prompt"] = self._act_prompt_txt.get("1.0", "end-1c").strip() or cur["prompt"]

    def _on_action_select(self, event):
        sel = self._act_listbox.curselection()
        if not sel:
            return
        self._commit_current_action()
        self._selected_action_idx = sel[0]
        self._load_action_fields(self._selected_action_idx)

    def _act_add(self):
        self._commit_current_action()
        self._edited_actions.append({
            "label": "✨  Nueva acción",
            "prompt": "Procesa el siguiente texto:",
            "section": "Personalizadas",
            "bootstyle": "info-outline",
            "shortcut": "",
            "auto_replace": False,
        })
        self._selected_action_idx = len(self._edited_actions) - 1
        self._refresh_actions_listbox()

    def _act_move(self, delta: int):
        idx = self._selected_action_idx
        new_idx = idx + delta
        if not (0 <= idx < len(self._edited_actions) and 0 <= new_idx < len(self._edited_actions)):
            return
        self._commit_current_action()
        self._edited_actions[idx], self._edited_actions[new_idx] = (
            self._edited_actions[new_idx], self._edited_actions[idx]
        )
        self._selected_action_idx = new_idx
        self._refresh_actions_listbox()

    def _act_delete(self):
        if len(self._edited_actions) <= 1:
            self._status("⚠️ Debe quedar al menos una acción.", _WARN)
            return
        idx = self._selected_action_idx
        if 0 <= idx < len(self._edited_actions):
            self._edited_actions.pop(idx)
            self._selected_action_idx = min(idx, len(self._edited_actions) - 1)
            self._refresh_actions_listbox()

    def _save_visual_actions(self):
        self._commit_current_action()
        try:
            warnings = save_actions(self._edited_actions)
            self._edited_actions, _ = load_actions()
            self._refresh_actions_listbox()
            if warnings:
                self._status(f"⚠️ Acciones guardadas con avisos: {warnings[0]}", _WARN)
            else:
                self._status("✅ Acciones guardadas en actions.json.", _FM_ACCENT)
        except Exception as e:
            self._status(f"❌ Error al guardar acciones: {e}", "#ef4444")

    def _build_general_tab(self, tab):
        hotkey_row = tk.Frame(tab, bg=_FM_BG)
        hotkey_row.pack(fill=X, pady=(0, 14))
        tk.Label(hotkey_row, text="Atajo global:  ",
                 font=(UI_FONT, 10, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(side=LEFT)
        current_hk = ConfigManager.get("hotkey") or DEFAULT_HOTKEY
        self.hotkey_var = tk.StringVar(value=current_hk)
        presets = list(HOTKEY_PRESETS)
        if current_hk not in presets:
            presets.insert(0, current_hk)
        tb.Combobox(hotkey_row, textvariable=self.hotkey_var, values=presets,
                    style="Escriba.TCombobox", font=(MONO_FONT, 9), width=18).pack(side=LEFT)

        self.streaming_var = tk.BooleanVar(value=bool(ConfigManager.get("streaming", True)))
        tb.Checkbutton(tab, text="  Mostrar la respuesta mientras se genera (streaming)",
                       variable=self.streaming_var,
                       bootstyle="warning").pack(anchor=W, pady=(0, 10))

        self.autostart_var = tk.BooleanVar(value=StartupManager.is_enabled())
        tb.Checkbutton(tab, text="  Iniciar automáticamente al iniciar sesión",
                       variable=self.autostart_var,
                       bootstyle="warning").pack(anchor=W, pady=(0, 16))

        tk.Frame(tab, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 14))
        self._title(tab, "Acciones del menú")
        self._hint(tab, "Puedes editar las acciones en la pestaña 'Acciones' o abrir actions.json "
                        "directamente. Los cambios se aplican al abrir el menú.", pady=(0, 10))
        act_row = tk.Frame(tab, bg=_FM_BG)
        act_row.pack(fill=X)
        tb.Button(act_row, text="📝  Abrir actions.json", style="Escriba.TButton",
                  command=self._edit_actions).pack(side=LEFT, expand=True, fill=X, padx=(0, 6), ipady=3)
        tb.Button(act_row, text="↺  Restaurar predeterminadas", style="Escriba.TButton",
                  command=self._reset_actions).pack(side=LEFT, expand=True, fill=X, ipady=3)

    # ── Estado ──────────────────────────────────────────────
    def _status(self, text: str, color: str = _FM_MUTED):
        self.status_var.set(text)
        self.status_lbl.configure(fg=color)

    def _alive(self) -> bool:
        return bool(self.window and self.window.winfo_exists())

    # ── Modelos de Gemini ───────────────────────────────────
    def _async_fetch_models(self):
        key = self.api_key_var.get().strip()
        models = GeminiClient.fetch_available_models(key)
        if self._alive():
            self.app.schedule(self._update_model_combobox, models)

    def _refresh_models(self):
        key = self.api_key_var.get().strip()
        if not key:
            self._status("⚠️ Introduce tu API Key de Gemini para descargar los modelos.", _WARN)
            return
        self._status("⏳ Consultando modelos disponibles...")
        self.refresh_btn.configure(state="disabled")

        def task():
            models, err = GeminiClient.fetch_models_with_status(key)
            self.app.schedule(self._on_models_refreshed, models, err)

        threading.Thread(target=task, daemon=True).start()

    def _on_models_refreshed(self, models: list[str], error: str | None = None):
        if not self._alive():
            return
        self.refresh_btn.configure(state="normal")
        self._update_model_combobox(models)
        if error:
            self._status(f"⚠️ No se pudieron consultar los modelos ({error}). Se muestran los predeterminados.", _WARN)
        else:
            self._status(f"✅ Se encontraron {len(models)} modelos de Gemini.", _FM_ACCENT)

    def _update_model_combobox(self, models: list[str]):
        if not self._alive():
            return
        self.model_cb["values"] = models
        if self.model_var.get() not in models:
            self.model_var.set(models[0] if models else GEMINI_DEFAULT_MODEL)

    # ── Modelos del proveedor alternativo ───────────────────
    def _refresh_alt_models(self):
        base = self.alt_url_var.get().strip()
        key = self.alt_key_var.get().strip()
        if not base:
            self._status("⚠️ Escribe la URL base del proveedor alternativo.", _WARN)
            return
        self._status(f"⏳ Consultando modelos en {base}…")
        self.alt_refresh_btn.configure(state="disabled")

        def task():
            models = OpenAICompatibleClient.fetch_available_models(base, key)
            self.app.schedule(self._on_alt_models, models)

        threading.Thread(target=task, daemon=True).start()

    def _on_alt_models(self, models: list[str]):
        if not self._alive():
            return
        self.alt_refresh_btn.configure(state="normal")
        if not models:
            self._status("⚠️ No se pudieron listar modelos. Revisa la URL, la clave o escribe el modelo a mano.", _WARN)
            return
        self.alt_model_cb["values"] = models
        if self.alt_model_var.get() not in models:
            self.alt_model_var.set(models[0])
        self._status(f"✅ Se encontraron {len(models)} modelos.", _FM_ACCENT)

    # ── Acciones ────────────────────────────────────────────
    def _edit_actions(self):
        try:
            path = write_defaults()
            open_in_editor(path)
            self._status(f"📝 Editando {path}", _FM_ACCENT)
        except Exception as e:
            self._status(f"❌ No se pudo abrir actions.json: {e}", "#ef4444")

    def _reset_actions(self):
        if not messagebox.askyesno(
            APP_NAME, "¿Reemplazar actions.json con las acciones predeterminadas?\n"
                      "Se perderán tus acciones personalizadas.", parent=self.window):
            return
        try:
            write_defaults(overwrite=True)
            self._edited_actions, _ = load_actions()
            self._selected_action_idx = 0 if self._edited_actions else -1
            self._refresh_actions_listbox()
            self._status("✅ Acciones restauradas a las predeterminadas.", _FM_ACCENT)
        except Exception as e:
            self._status(f"❌ No se pudo restaurar: {e}", "#ef4444")

    # ── Guardar ─────────────────────────────────────────────
    def _save(self):
        provider = self.provider_var.get()
        alt_url = self.alt_url_var.get().strip().rstrip("/")
        alt_model = self.alt_model_var.get().strip()
        gemini_key = self.api_key_var.get().strip()

        if provider == "openai" and not (alt_url and alt_model):
            self._status("⚠️ Para usar el proveedor alternativo indica la URL base y el modelo.", _WARN)
            return
        note = ""
        if provider == "gemini" and not gemini_key and not self.fallback_var.get():
            note = "\n⚠️ Sin API Key de Gemini no se podrán procesar solicitudes."

        prev_hotkey = ConfigManager.get("hotkey") or DEFAULT_HOTKEY
        new_hotkey = self.hotkey_var.get().strip() or DEFAULT_HOTKEY

        ConfigManager.set_api_key(gemini_key)
        ConfigManager.set("model", self.model_var.get().strip() or GEMINI_DEFAULT_MODEL)
        ConfigManager.set("provider", provider)
        ConfigManager.set("openai_base_url", alt_url)
        ConfigManager.set("openai_model", alt_model)
        ConfigManager.set_openai_api_key(self.alt_key_var.get().strip())
        ConfigManager.set("fallback_enabled", bool(self.fallback_var.get()))
        ConfigManager.set("streaming", bool(self.streaming_var.get()))
        ConfigManager.set("hotkey", new_hotkey)
        if new_hotkey != prev_hotkey and hasattr(self.app, "reload_hotkey"):
            self.app.reload_hotkey(new_hotkey)

        try:
            if self.autostart_var.get():
                StartupManager.enable()
            else:
                StartupManager.disable()
            ConfigManager.set("autostart", bool(self.autostart_var.get()))
        except OSError as e:
            self._status(f"⚠️ No se pudo cambiar el inicio automático: {e}", _WARN)
            return

        if note:
            self._status("✅  Configuración guardada." + note, _WARN)
            return  # se deja abierta para que el aviso se pueda leer
        self._status("✅  Configuración guardada correctamente.", _FM_ACCENT)
        self.window.after(900, self._close)

    def _close(self):
        if self._alive():
            self.window.destroy()
        self.window = None
