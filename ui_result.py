"""
Escriba — Ejecución de acciones de IA y ventana de resultados.

Flujo con streaming:
  ThinkingWindow → (primer fragmento) → ResultWindow en modo "generando",
  que recibe los fragmentos → finish() habilita los botones.
Sin streaming (o si la respuesta llega de golpe) se abre ResultWindow al final.
"""

from __future__ import annotations

import threading
import time
import tkinter as tk
from typing import TYPE_CHECKING

import pyperclip
import ttkbootstrap as tb
from ttkbootstrap.constants import *

from ai_clients import PROVIDER_LABELS, generate_text
from config import ConfigManager
from constants import APP_NAME, OPENAI_DEFAULT_MODEL
from plataforma import activate_window, send_paste
from ui_common import (
    _FM_ACCENT, _FM_BG, _FM_CARD, _FM_MUTED, _FM_SEP, _FM_TEXT, UI_FONT,
    ThinkingWindow, apply_dark_style, center_window,
)

if TYPE_CHECKING:
    from escriba import EscribaApp

CUSTOM_PROMPT_LABEL = "✏️  Prompt personalizado"


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

    def __init__(self, app: EscribaApp, prompt: str, text: str, prev_hwnd, thinking: ThinkingWindow, label: str):
        self.app = app
        self.prompt = prompt
        self.text = text
        self.prev_hwnd = prev_hwnd
        self.thinking = thinking
        self.label = label
        self.window: ResultWindow | None = None
        self._opened = False  # solo lo toca el hilo de trabajo

    # ── Hilo de trabajo ─────────────────────────────────────
    def on_chunk(self, piece: str):
        if not self._opened:
            self._opened = True
            self.app.schedule(self._open_streaming)
        self.app.schedule(self._append, piece)

    # ── Hilo de Tk ──────────────────────────────────────────
    def _open_streaming(self):
        self.thinking.close()
        self.window = ResultWindow(
            self.app, "", self.prev_hwnd,
            prompt=self.prompt, selected_text=self.text,
            label=self.label, streaming=True,
        )

    def _append(self, piece: str):
        if self.window:
            self.window.append_chunk(piece)

    def finish(self, result: str, provider: str):
        self.thinking.close()
        if self.window:
            self.window.finish(result, provider)
        else:
            ResultWindow(
                self.app, result, self.prev_hwnd,
                prompt=self.prompt, selected_text=self.text,
                label=self.label, provider=provider,
            )

    def fail(self, message: str):
        self.thinking.close()
        if self.window:
            self.window.mark_failed()
        self.app.tooltip.show(f"❌ {message[:180]}", "danger", 6000)


def run_ai_action(app: EscribaApp, prompt: str, text: str, prev_hwnd,
                  thinking: ThinkingWindow, label: str = CUSTOM_PROMPT_LABEL):
    """Ejecuta una acción de IA (llamar en un hilo secundario)."""
    session = _ResultSession(app, prompt, text, prev_hwnd, thinking, label)
    streaming = bool(ConfigManager.get("streaming", True))

    def on_retry(attempt, max_retries, delay, reason):
        sec = max(1, int(round(delay)))
        thinking.update_status(f"⏳ Modelo ocupado ({attempt}/{max_retries}). Reintentando en {sec}s…")

    try:
        result, provider = generate_text(
            prompt, text,
            on_retry=on_retry,
            on_chunk=session.on_chunk if streaming else None,
            on_status=thinking.update_status,
        )
        app.history.add(label, prompt, text, result, provider)
        app.schedule(session.finish, result, provider)
    except Exception as e:
        app.schedule(session.fail, str(e))


def start_ai_action(app: EscribaApp, prompt: str, text: str, prev_hwnd, label: str,
                    status: str | None = None):
    """Muestra el indicador de progreso y lanza la acción en un hilo."""
    thinking = ThinkingWindow(app.root, status or f"{label.strip()}…")
    threading.Thread(
        target=run_ai_action,
        args=(app, prompt, text, prev_hwnd, thinking, label),
        daemon=True,
    ).start()


# ─────────────────────────────────────────────────────────────
# Ventana de Resultados
# ─────────────────────────────────────────────────────────────
class ResultWindow:
    """Muestra el resultado de la IA con opciones de copiar, sustituir y regenerar."""

    def __init__(self, app: EscribaApp, result: str, prev_hwnd,
                 prompt: str = "", selected_text: str = "",
                 provider: str = "gemini", label: str = CUSTOM_PROMPT_LABEL,
                 streaming: bool = False):
        self.app = app
        self.result = result
        self.prev_hwnd = prev_hwnd
        self.prompt = prompt
        self.selected_text = selected_text
        self.provider = provider
        self.label = label
        self.streaming = streaming

        win = tb.Toplevel(app.root)
        win.title(f"{APP_NAME} — Resultado")
        win.attributes("-topmost", True)
        win.resizable(True, True)
        apply_dark_style(win)
        self.window = win
        center_window(win, 580, 420)

        frame = tk.Frame(win, bg=_FM_BG, padx=16, pady=12)
        frame.pack(fill=BOTH, expand=True)

        # Header
        hdr = tk.Frame(frame, bg=_FM_BG)
        hdr.pack(fill=X, pady=(0, 8))
        tk.Label(hdr, text="✦  Texto generado",
                 font=(UI_FONT, 12, "bold"), bg=_FM_BG, fg=_FM_TEXT).pack(side=LEFT)

        badge_f = tk.Frame(hdr, bg=_FM_ACCENT)
        badge_f.pack(side=RIGHT)
        self._badge = tk.Label(
            badge_f,
            text="⏳ Generando…" if streaming else provider_badge(provider),
            font=(UI_FONT, 8, "bold"), bg=_FM_ACCENT, fg=_FM_BG, padx=7, pady=3,
        )
        self._badge.pack()

        tk.Frame(frame, bg=_FM_SEP, height=1).pack(fill=X, pady=(0, 10))

        # Botones — se empaquetan primero con side=BOTTOM para garantizar visibilidad
        btn_bot = tk.Frame(frame, bg=_FM_BG)
        btn_bot.pack(side=BOTTOM, fill=X, pady=(6, 0))

        self._copy_btn = tb.Button(btn_bot, text="📋  Copiar al portapapeles",
                                   bootstyle="secondary-outline", command=self._copy)
        self._copy_btn.pack(side=LEFT, expand=True, fill=X, padx=(0, 6), ipady=4)

        tb.Button(btn_bot, text="✕  Cerrar", bootstyle="danger-outline",
                  command=win.destroy).pack(side=LEFT, expand=True, fill=X, ipady=4)

        btn_mid = tk.Frame(frame, bg=_FM_BG)
        btn_mid.pack(side=BOTTOM, fill=X, pady=(0, 6))

        self._regen_btn = tb.Button(btn_mid, text="🔄  Volver a generar",
                                    bootstyle="warning", command=self._regenerate)
        self._regen_btn.pack(side=LEFT, expand=True, fill=X, padx=(0, 6), ipady=4)

        self._replace_btn = tb.Button(btn_mid, text="⬅️  Sustituir texto seleccionado",
                                      bootstyle="warning", command=self._replace)
        self._replace_btn.pack(side=LEFT, expand=True, fill=X, ipady=4)

        # Área de texto editable
        txt_frame = tk.Frame(frame, bg=_FM_BG)
        txt_frame.pack(fill=BOTH, expand=True, pady=(0, 6))

        scrollbar = tb.Scrollbar(txt_frame, bootstyle="warning-round")
        scrollbar.pack(side=RIGHT, fill=Y)

        self.text_widget = tk.Text(
            txt_frame,
            font=(UI_FONT, 10),
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

        if streaming:
            # Mientras llega el texto no se puede editar ni actuar sobre él.
            self.text_widget.configure(state="disabled", fg=_FM_MUTED)
            self._set_actions_enabled(False)
        else:
            self._set_actions_enabled(True)

        win.protocol("WM_DELETE_WINDOW", win.destroy)

    # ── Estado ──────────────────────────────────────────────
    def _alive(self) -> bool:
        return bool(self.window and self.window.winfo_exists())

    def _set_actions_enabled(self, enabled: bool):
        self._copy_btn.configure(state="normal" if enabled else "disabled")
        self._regen_btn.configure(state="normal" if enabled and self.prompt else "disabled")
        # Sin ventana de origen (p. ej. abierto desde el historial) no hay dónde sustituir.
        self._replace_btn.configure(state="normal" if enabled and self.prev_hwnd else "disabled")

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
        self.streaming = False
        if not self._alive():
            return
        self.text_widget.configure(state="normal", fg=_FM_TEXT)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", result)
        self._badge.configure(text=provider_badge(provider))
        self._set_actions_enabled(True)
        self.text_widget.focus_set()

    def mark_failed(self):
        self.streaming = False
        if not self._alive():
            return
        self.text_widget.configure(state="normal", fg=_FM_TEXT)
        self._badge.configure(text="⚠️ Respuesta interrumpida")
        self._set_actions_enabled(True)

    # ── Acciones ────────────────────────────────────────────
    def _copy(self):
        text = self.text_widget.get("1.0", tk.END).strip()
        pyperclip.copy(text)
        self.app.tooltip.show("📋 Copiado al portapapeles.", "info", 2000)

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
            self.app.schedule(self.app.tooltip.show, "✅ Texto sustituido.", "success")
        except Exception as e:
            self.app.schedule(self.app.tooltip.show, f"❌ Error al sustituir: {e}", "danger")

    def _regenerate(self):
        self.window.destroy()
        start_ai_action(self.app, self.prompt, self.selected_text, self.prev_hwnd,
                        self.label, status="🔄  Volver a generar…")
