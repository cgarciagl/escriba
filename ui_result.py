"""
Escriba — Ejecución de acciones de IA y ventana de resultados.

Flujo con streaming:
  ThinkingWindow (con "Cancelar") → primer fragmento → ResultWindow en modo
  "generando" (con "Detener") → finish() habilita las acciones.
Sin streaming (o si la respuesta llega de golpe) se abre ResultWindow al final.

Atajos de la ventana de resultado (⌘ en lugar de Ctrl en macOS):
  Ctrl+Enter  sustituir el texto original
  Ctrl+Shift+C copiar
  Ctrl+R      volver a generar
  Ctrl+O      alternar resultado / original
  Esc         cerrar
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from typing import TYPE_CHECKING

import pyperclip
import ttkbootstrap as tb
from ttkbootstrap.constants import *

from ai_clients import PROVIDER_LABELS, CancelledByUser, generate_text, needs_configuration
from config import ConfigManager
from constants import APP_NAME, OPENAI_DEFAULT_MODEL
from plataforma import PRIMARY_MODIFIER_TK, activate_window, send_paste, shortcut_label
from ui_common import (
    _FM_ACCENT, _FM_BG, _FM_CARD, _FM_MUTED, _FM_SEP, _FM_TEXT, UI_FONT,
    ThinkingWindow, apply_dark_style, center_window,
)

if TYPE_CHECKING:
    from escriba import EscribaApp

CUSTOM_PROMPT_LABEL = "✏️  Prompt personalizado"
_MOD = PRIMARY_MODIFIER_TK


def provider_badge(provider: str) -> str:
    """Texto del badge: proveedor + modelo usado."""
    if provider == "openai":
        model = ConfigManager.get("openai_model", OPENAI_DEFAULT_MODEL)
    else:
        model = ConfigManager.get_model()
    return f"⚡ {PROVIDER_LABELS.get(provider, provider)} ({model})"


# ─────────────────────────────────────────────────────────────
# Sesión de una petición (puente entre el hilo de trabajo y Tk)
# ─────────────────────────────────────────────────────────────
class _ResultSession:
    """Los métodos on_* se llaman desde el hilo de trabajo; el resto, en Tk."""

    def __init__(self, app: EscribaApp, prompt: str, text: str, prev_hwnd, label: str):
        self.app = app
        self.prompt = prompt
        self.text = text
        self.prev_hwnd = prev_hwnd
        self.label = label
        self.cancel_event = threading.Event()
        self.thinking: ThinkingWindow | None = None
        self.window: ResultWindow | None = None
        self._opened = False  # solo lo toca el hilo de trabajo

    def cancel(self):
        self.cancel_event.set()

    # ── Hilo de trabajo ─────────────────────────────────────
    def on_chunk(self, piece: str):
        if not self._opened:
            self._opened = True
            self.app.schedule(self._open_streaming)
        self.app.schedule(self._append, piece)

    # ── Hilo de Tk ──────────────────────────────────────────
    def _close_thinking(self):
        if self.thinking:
            self.thinking.close()

    def _open_streaming(self):
        self._close_thinking()
        self.window = ResultWindow(
            self.app, "", self.prev_hwnd,
            prompt=self.prompt, selected_text=self.text,
            label=self.label, streaming=True, on_stop=self.cancel,
        )

    def _append(self, piece: str):
        if self.window:
            self.window.append_chunk(piece)

    def finish(self, result: str, provider: str):
        self._close_thinking()
        if self.window:
            self.window.finish(result, provider)
        else:
            ResultWindow(
                self.app, result, self.prev_hwnd,
                prompt=self.prompt, selected_text=self.text,
                label=self.label, provider=provider,
            )

    def fail(self, exc: Exception):
        self._close_thinking()
        if isinstance(exc, CancelledByUser):
            if self.window:
                self.window.mark_stopped()
            else:
                self.app.tooltip.show("Petición cancelada.", "info", 2500)
            return

        if self.window:
            self.window.mark_failed()
        if needs_configuration(exc):
            action = ("Abrir configuración", self.app.open_config)
        else:
            action = ("Reintentar", lambda: start_ai_action(
                self.app, self.prompt, self.text, self.prev_hwnd, self.label))
        self.app.tooltip.show(str(exc), "danger", action=action)


def run_ai_action(app: EscribaApp, session: _ResultSession):
    """Ejecuta la petición de una sesión (llamar en un hilo secundario)."""
    streaming = bool(ConfigManager.get("streaming", True))
    thinking = session.thinking

    def on_retry(attempt, max_retries, delay, reason):
        sec = max(1, int(round(delay)))
        if thinking:
            thinking.update_status(f"⏳ Modelo ocupado ({attempt}/{max_retries}). Reintentando en {sec} s…")

    try:
        result, provider = generate_text(
            session.prompt, session.text,
            on_retry=on_retry,
            on_chunk=session.on_chunk if streaming else None,
            on_status=thinking.update_status if thinking else None,
            cancel_event=session.cancel_event,
        )
        app.history.add(session.label, session.prompt, session.text, result, provider)
        app.schedule(session.finish, result, provider)
    except Exception as e:
        app.schedule(session.fail, e)


def start_ai_action(app: EscribaApp, prompt: str, text: str, prev_hwnd, label: str,
                    status: str | None = None) -> _ResultSession:
    """Muestra el indicador de progreso y lanza la acción en un hilo."""
    session = _ResultSession(app, prompt, text, prev_hwnd, label)
    session.thinking = ThinkingWindow(app.root, status or f"{label.strip()}…", on_cancel=session.cancel)
    threading.Thread(target=run_ai_action, args=(app, session), daemon=True).start()
    return session


# ─────────────────────────────────────────────────────────────
# Ventana de Resultados
# ─────────────────────────────────────────────────────────────
class ResultWindow:
    """Resultado de la IA: sustituir (acción principal), copiar, regenerar y comparar."""

    def __init__(self, app: EscribaApp, result: str, prev_hwnd,
                 prompt: str = "", selected_text: str = "",
                 provider: str = "gemini", label: str = CUSTOM_PROMPT_LABEL,
                 streaming: bool = False, on_stop=None):
        self.app = app
        self.result = result
        self.prev_hwnd = prev_hwnd
        self.prompt = prompt
        self.selected_text = selected_text
        self.provider = provider
        self.label = label
        self.streaming = streaming
        self._on_stop = on_stop
        self.can_replace = bool(prev_hwnd)

        win = tb.Toplevel(app.root)
        win.title(f"{APP_NAME} — {label.split('  ', 1)[-1].strip()}")
        win.attributes("-topmost", True)
        win.resizable(True, True)
        apply_dark_style(win)
        self.window = win
        center_window(win, 600, 440)

        frame = tk.Frame(win, bg=_FM_BG, padx=16, pady=12)
        frame.pack(fill=BOTH, expand=True)

        # ── Encabezado ──────────────────────────────────────
        hdr = tk.Frame(frame, bg=_FM_BG)
        hdr.pack(fill=X, pady=(0, 8))
        tk.Label(hdr, text=f"✦  {label.split('  ', 1)[-1].strip()}",
                 font=(UI_FONT, 12, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(side=LEFT)
        badge_f = tk.Frame(hdr, bg=_FM_ACCENT)
        badge_f.pack(side=RIGHT)
        self._badge = tk.Label(
            badge_f, text="⏳ Generando…" if streaming else provider_badge(provider),
            font=(UI_FONT, 8, "bold"), bg=_FM_ACCENT, fg=_FM_BG, padx=7, pady=3,
        )
        self._badge.pack()

        # ── Selector Resultado / Original + Detener ─────────
        bar = tk.Frame(frame, bg=_FM_BG)
        bar.pack(fill=X, pady=(0, 6))
        self.view_var = tk.StringVar(value="result")
        tb.Radiobutton(bar, text="Resultado", value="result", variable=self.view_var,
                       style="Escriba.Toolbutton", command=self._switch_view).pack(side=LEFT)
        tb.Radiobutton(bar, text="Original", value="original", variable=self.view_var,
                       style="Escriba.Toolbutton", command=self._switch_view).pack(side=LEFT)
        tk.Label(bar, text=shortcut_label("Ctrl+O"), font=(UI_FONT, 8),
                 bg=_FM_BG, fg=_FM_MUTED).pack(side=LEFT, padx=(8, 0))
        self._stop_btn = tb.Button(bar, text="⏹  Detener", style="Escriba.TButton",
                                   command=self._stop)
        if streaming and on_stop:
            self._stop_btn.pack(side=RIGHT)

        # ── Botones (se empaquetan antes para que siempre se vean) ──
        tk.Frame(frame, bg=_FM_SEP, height=1).pack(side=BOTTOM, fill=X, pady=(8, 0))
        btns = tk.Frame(frame, bg=_FM_BG)
        btns.pack(side=BOTTOM, fill=X, pady=(8, 0))

        primary_is_replace = self.can_replace
        self._replace_btn = tb.Button(
            btns, text=f"⬅  Sustituir texto   {shortcut_label('Ctrl+Enter')}",
            bootstyle="warning", command=self._replace,
        )
        copy_text = f"📋  Copiar   {shortcut_label('Ctrl+Shift+C')}"
        if primary_is_replace:
            self._copy_btn = tb.Button(btns, text=copy_text, style="Escriba.TButton", command=self._copy)
        else:
            self._copy_btn = tb.Button(btns, text=copy_text, bootstyle="warning", command=self._copy)
        self._regen_btn = tb.Button(
            btns, text=f"🔄  Regenerar   {shortcut_label('Ctrl+R')}",
            style="Escriba.TButton", command=self._regenerate,
        )

        if primary_is_replace:
            self._replace_btn.pack(side=RIGHT, ipady=4)
            self._copy_btn.pack(side=LEFT, ipady=2)
        else:
            self._copy_btn.pack(side=RIGHT, ipady=4)
        self._regen_btn.pack(side=LEFT, ipady=2, padx=(6, 0))
        tk.Label(btns, text="Esc cierra", font=(UI_FONT, 8), bg=_FM_BG, fg=_FM_MUTED
                 ).pack(side=LEFT, padx=(10, 0))

        # ── Área de texto: resultado (editable) y original (solo lectura) ──
        self.txt_frame = tk.Frame(frame, bg=_FM_BG)
        self.txt_frame.pack(fill=BOTH, expand=True)
        self.text_widget = self._make_text(self.txt_frame, result)
        self.original_widget = self._make_text(self.txt_frame, selected_text)
        self.original_widget.configure(state="disabled", fg=_FM_MUTED)
        self._scroll = tb.Scrollbar(self.txt_frame, bootstyle="warning-round")
        self._show_widget(self.text_widget)

        self._bind_keys(win)
        if streaming:
            # Mientras llega el texto no se puede editar ni actuar sobre él.
            self.text_widget.configure(state="disabled", fg=_FM_MUTED)
            self._set_actions_enabled(False)
        else:
            self._set_actions_enabled(True)
        self.text_widget.focus_set()
        win.protocol("WM_DELETE_WINDOW", win.destroy)

    # ── Construcción ────────────────────────────────────────
    @staticmethod
    def _make_text(parent, content: str) -> tk.Text:
        widget = tk.Text(parent, font=(UI_FONT, 10), wrap=tk.WORD, relief="flat",
                         bg=_FM_CARD, fg=_FM_TEXT, insertbackground=_FM_ACCENT,
                         padx=10, pady=10, undo=True)
        widget.insert("1.0", content)
        return widget

    def _show_widget(self, widget: tk.Text):
        for w in (self.text_widget, self.original_widget, self._scroll):
            w.pack_forget()
        self._scroll.pack(side=RIGHT, fill=Y)
        widget.pack(fill=BOTH, expand=True)
        widget.configure(yscrollcommand=self._scroll.set)
        self._scroll.configure(command=widget.yview)

    def _bind_keys(self, win):
        def stop(handler):
            def wrapper(event):
                handler()
                return "break"
            return wrapper

        bindings = {
            f"<{_MOD}-Return>": self._replace_if_enabled,
            f"<{_MOD}-C>": self._copy_if_enabled,       # Ctrl+Shift+C (C mayúscula = con Shift)
            f"<{_MOD}-r>": self._regenerate_if_enabled,
            f"<{_MOD}-o>": self._toggle_view,
            "<Escape>": win.destroy,
        }
        for seq, handler in bindings.items():
            win.bind(seq, stop(handler))
            self.text_widget.bind(seq, stop(handler))
            self.original_widget.bind(seq, stop(handler))

    # ── Vista ───────────────────────────────────────────────
    def _switch_view(self):
        if self.view_var.get() == "original":
            self._show_widget(self.original_widget)
        else:
            self._show_widget(self.text_widget)
            self.text_widget.focus_set()

    def _toggle_view(self):
        self.view_var.set("original" if self.view_var.get() == "result" else "result")
        self._switch_view()

    # ── Estado ──────────────────────────────────────────────
    def _alive(self) -> bool:
        return bool(self.window and self.window.winfo_exists())

    def _set_actions_enabled(self, enabled: bool):
        self._actions_enabled = enabled
        state = "normal" if enabled else "disabled"
        self._copy_btn.configure(state=state)
        self._regen_btn.configure(state="normal" if enabled and self.prompt else "disabled")
        self._replace_btn.configure(state="normal" if enabled and self.can_replace else "disabled")

    def _end_streaming(self):
        self.streaming = False
        self._stop_btn.pack_forget()
        self.text_widget.configure(state="normal", fg=_FM_TEXT)
        self._set_actions_enabled(True)

    # ── Streaming ───────────────────────────────────────────
    def append_chunk(self, piece: str):
        if not self._alive():
            return
        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, piece)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state="disabled")

    def finish(self, result: str, provider: str):
        self.result = result
        self.provider = provider
        if not self._alive():
            self.streaming = False
            return
        self._end_streaming()
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", result)
        self._badge.configure(text=provider_badge(provider))
        self.text_widget.focus_set()

    def mark_failed(self):
        if not self._alive():
            self.streaming = False
            return
        self._end_streaming()
        self._badge.configure(text="⚠️ Respuesta interrumpida")

    def mark_stopped(self):
        if not self._alive():
            self.streaming = False
            return
        self._end_streaming()
        self._badge.configure(text="⏹ Detenido")

    def _stop(self):
        self._stop_btn.configure(state="disabled", text="Deteniendo…")
        if self._on_stop:
            self._on_stop()

    # ── Acciones ────────────────────────────────────────────
    def _replace_if_enabled(self):
        if self._actions_enabled and self.can_replace:
            self._replace()

    def _copy_if_enabled(self):
        if self._actions_enabled:
            self._copy()

    def _regenerate_if_enabled(self):
        if self._actions_enabled and self.prompt:
            self._regenerate()

    def _copy(self):
        text = self.text_widget.get("1.0", tk.END).strip()
        pyperclip.copy(text)
        self.app.tooltip.show("Copiado al portapapeles.", "success", 2000)

    def _replace(self):
        text = self.text_widget.get("1.0", tk.END).strip()
        self.window.destroy()
        threading.Thread(target=self._do_replace, args=(text,), daemon=True).start()

    def _do_replace(self, text: str):
        original_clip = ""
        try:
            original_clip = pyperclip.paste()
        except Exception:
            pass
        try:
            pyperclip.copy(text)
            activate_window(self.prev_hwnd)
            send_paste()
            # Dar tiempo a la app destino a leer el portapapeles y restaurarlo.
            time.sleep(0.30)
            if original_clip:
                pyperclip.copy(original_clip)
            self.app.schedule(self.app.tooltip.show, "Texto sustituido.", "success")
        except Exception as e:
            self.app.schedule(self.app.tooltip.show, f"No se pudo sustituir el texto: {e}", "danger")

    def _regenerate(self):
        self.window.destroy()
        start_ai_action(self.app, self.prompt, self.selected_text, self.prev_hwnd,
                        self.label, status="🔄  Volviendo a generar…")
