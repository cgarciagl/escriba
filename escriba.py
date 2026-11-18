"""
Escriba - Asistente de Texto con IA para Windows, macOS y Linux v1.0.4
==================================================================
Hotkey: Win+Alt+E en Windows (RegisterHotKey, ver hotkey.py) y Ctrl+Cmd+E en
macOS (ver macos.py). Lo dependiente del sistema se accede vía plataforma.py.

Stack: ttkbootstrap, pystray, Pillow, pyperclip, ctypes, requests
"""

import os
import time
import threading
import webbrowser

import ttkbootstrap as tb
import pyperclip

from actions import expand_prompt_vars
from constants import APP_NAME, APP_VERSION, DEFAULT_REPEAT_HOTKEY, HISTORY_FILE
from config import ConfigManager
from ai_clients import is_ready
from history import History
from ui_common import configure_styles
from ui_windows import (
    AboutWindow, ConfigWindow, FloatingMenu, ResultWindow, ThinkingWindow,
    TooltipNotification, SplashBanner, UpdateDialog, start_ai_action,
)
from tray import TrayIconManager
from plataforma import (
    HotkeyManager, StartupManager, acquire_single_instance, active_hotkey_label,
    clipboard_copy, clipboard_has_non_text, clipboard_paste, enable_dpi_awareness,
    format_hotkey_label, get_foreground_app_name, get_foreground_window,
    has_wayland_tools, init_app, is_wayland, release_single_instance, send_copy,
)
from updater import (
    ReleaseInfo, UpdateCancelled, apply_update_and_restart, can_self_update,
    check_for_update, download_and_prepare, should_auto_check,
)


# ─────────────────────────────────────────────────────────────
# Aplicación Principal
# ─────────────────────────────────────────────────────────────
class EscribaApp:
    """Orquestador principal: conecta hotkey, tray, y ventanas UI."""

    def __init__(self):
        enable_dpi_awareness()  # Windows: texto nítido con escalado (antes de crear Tk)
        self.root = tb.Window(themename="vapor")
        init_app()  # macOS: sin ícono en el Dock
        configure_styles(self.root)
        self.root.title(APP_NAME)
        self.root.withdraw()

        persist_hist = bool(ConfigManager.get("persist_history", True))
        self.history = History(storage_path=HISTORY_FILE if persist_hist else None)
        self.config_window = ConfigWindow(self)
        self.about_window = AboutWindow(self.root)
        self.floating_menu = FloatingMenu(self)
        self.tooltip = TooltipNotification(self.root)
        self.tray = TrayIconManager(self)
        # El refresco del menú se hace en el hilo principal (obligatorio en macOS).
        self.history.on_change = lambda: self.schedule(self.tray.refresh)
        self.hotkey = HotkeyManager(self.root, self._on_hotkey)
        self.repeat_hotkey = HotkeyManager(self.root, self._on_repeat_hotkey, hotkey_id=2)
        self._last_action: dict | None = None
        self._lock = threading.Lock()

    def run(self):
        """Inicia la app: carga config, tray, hotkey y entra al mainloop."""
        config = ConfigManager.load()

        # Orquestar arranque automático si está activado en config
        if config.get("autostart"):
            StartupManager.enable()

        self.tray.start()
        SplashBanner(self.root)
        self.root.after(500, lambda: self._start_hotkeys(config))
        if is_wayland():
            self.root.after(2200, self._notify_wayland)
        # Primer arranque: sin proveedor configurado, guiar al usuario a Configuración.
        if not is_ready():
            self.root.after(1800, lambda: self.config_window.show(welcome=True))
        self.root.after(3500, self._maybe_check_updates)
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.mainloop()

    def _start_hotkeys(self, config: dict):
        self.hotkey.start(config.get("hotkey"))
        rep = (config.get("repeat_hotkey") or DEFAULT_REPEAT_HOTKEY or "").strip()
        if rep:
            self.repeat_hotkey.start(rep)

    def _notify_wayland(self):
        has_wl_copy, has_wtype = has_wayland_tools()
        if has_wl_copy and has_wtype:
            return
        missing = [
            name for ok, name in ((has_wl_copy, "wl-clipboard"), (has_wtype, "wtype")) if not ok
        ]
        self.tooltip.show(
            "⚠️ Sesión Wayland detectada.\n"
            f"Instala {' y '.join(missing)} para portapapeles y pegado nativo en Wayland.",
            "warning", 8000,
        )

    def _maybe_check_updates(self):
        """Comprueba si hay una nueva versión en GitHub (como máximo cada 24 h)."""
        if not should_auto_check():
            return

        def task():
            info, _ = check_for_update()
            if info:
                self.schedule(self._notify_update, info)

        threading.Thread(target=task, daemon=True).start()

    def _notify_update(self, info: ReleaseInfo):
        """Muestra una notificación discreta cuando hay una versión nueva."""
        msg = (
            f"🚀 Nueva versión disponible: Escriba v{info.version}\n"
            f"Estás usando la v{APP_VERSION}."
        )

        def _open_dialog():
            UpdateDialog(
                self.root, info,
                on_confirm=lambda: self.start_update(info),
                can_install=can_self_update(),
            ).show()

        if info.release_notes:
            action = ("Ver novedades", _open_dialog)
        elif can_self_update():
            action = ("Actualizar ahora", lambda: self.start_update(info))
        else:
            action = ("Ver release", lambda: webbrowser.open(info.html_url))
        self.tooltip.show(msg, "info", duration=15000, action=action)

    def start_update(self, info: ReleaseInfo):
        """Descarga la actualización con barra de progreso y reinicia la app."""
        if not can_self_update():
            webbrowser.open(info.html_url)
            return

        cancel_event = threading.Event()
        thinking = ThinkingWindow(
            self.root, f"Descargando Escriba v{info.version}…", on_cancel=cancel_event.set
        )

        def on_progress(pct: int | None):
            if pct is not None:
                thinking.update_status(f"Descargando Escriba v{info.version}… {pct} %")

        def task():
            try:
                prepared = download_and_prepare(
                    info, on_progress=on_progress, cancel_event=cancel_event
                )
            except UpdateCancelled:
                self.schedule(thinking.close)
                return
            except Exception as exc:
                self.schedule(self._on_update_error, thinking, info, str(exc))
                return

            def finish():
                thinking.close()
                try:
                    apply_update_and_restart(prepared, on_quit=self.quit_app)
                except Exception as exc:
                    self._on_update_error(None, info, str(exc))

            self.schedule(finish)

        threading.Thread(target=task, daemon=True).start()

    def _on_update_error(self, thinking, info: ReleaseInfo, error: str):
        if thinking:
            thinking.close()
        self.tooltip.show(
            f"❌ No se pudo completar la actualización:\n{error}",
            "danger",
            action=("Abrir descarga", lambda: webbrowser.open(info.html_url)),
        )

    def reload_hotkey(self, hotkey: str | None = None, repeat_hotkey: str | None = None):
        """Reinicia los listeners de atajos globales con las nuevas combinaciones."""
        self.hotkey.stop()
        self.repeat_hotkey.stop()
        self.tray.update_hotkey()

        def _restart():
            self.hotkey.start(hotkey)
            rep = (
                ConfigManager.get("repeat_hotkey", DEFAULT_REPEAT_HOTKEY)
                if repeat_hotkey is None
                else repeat_hotkey
            ) or ""
            if rep.strip():
                self.repeat_hotkey.start(rep.strip())

        self.root.after(120, _restart)

    def remember_last_action(
        self,
        prompt: str,
        label: str,
        auto_replace: bool = False,
        model: str = "",
        temperature: float | None = None,
        strip_markdown: bool = False,
    ):
        """Guarda la última acción ejecutada para el atajo de repetición rápida."""
        self._last_action = {
            "prompt": prompt,
            "label": label,
            "auto_replace": auto_replace,
            "model": model,
            "temperature": temperature,
            "strip_markdown": strip_markdown,
        }

    def open_config(self):
        self.config_window.show()

    def open_about(self):
        self.about_window.show()

    def open_history_entry(self, entry):
        """Reabre una respuesta del historial (sin ventana de origen: no se puede sustituir)."""
        ResultWindow(
            self, entry.result, None,
            prompt=entry.prompt, selected_text=entry.selected_text,
            provider=entry.provider, label=entry.label, model=entry.model,
        )

    def schedule(self, callback, *args):
        """Programa una tarea en el hilo principal de Tk (Law of Demeter)."""
        self.root.after(0, callback, *args)

    def quit_app(self):
        self.hotkey.stop()
        self.repeat_hotkey.stop()
        self.tray.stop()
        self.floating_menu.hide()
        self.tooltip.hide()
        release_single_instance()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def _on_hotkey(self, error=False):
        """Ejecutado al detectar el atajo global."""
        if error:
            self._notify_hotkey_error()
            return

        if not self._lock.acquire(blocking=False):
            return
        try:
            selected = self._capture_selected_text()
            self.schedule(self.floating_menu.show, selected)
        finally:
            self._lock.release()

    def _launch_repeat(self, prompt: str, selected: str, hwnd, last: dict):
        kwargs = {}
        if last.get("model"):
            kwargs["model"] = last["model"]
        if last.get("temperature") is not None:
            kwargs["temperature"] = last["temperature"]
        if last.get("strip_markdown"):
            kwargs["strip_markdown"] = True
        start_ai_action(
            self, prompt, selected, hwnd, last["label"],
            auto_replace=bool(last.get("auto_replace")),
            **kwargs,
        )

    def _on_repeat_hotkey(self, error=False):
        """Reejecuta la última acción sobre la selección actual sin abrir el menú."""
        if error:
            rep = ConfigManager.get("repeat_hotkey", DEFAULT_REPEAT_HOTKEY) or ""
            lbl = format_hotkey_label(rep) if rep else "repetir"
            self.tooltip.show(
                f"❌ Error: No se pudo registrar el atajo {lbl}.\n"
                "Es posible que otra aplicación lo esté usando.",
                "danger", 6000,
            )
            return

        if not self._lock.acquire(blocking=False):
            return
        try:
            hwnd = get_foreground_window()
            selected = self._capture_selected_text()
            last = self._last_action
            if not last:
                self.schedule(self.floating_menu.show, selected)
                return
            app_name = get_foreground_app_name(hwnd)
            expanded = expand_prompt_vars(last["prompt"], extra_vars={"app": app_name})
            self.schedule(self._launch_repeat, expanded, selected, hwnd, last)
        finally:
            self._lock.release()

    def _notify_hotkey_error(self):
        hk = active_hotkey_label()
        self.tooltip.show(
            f"❌ Error: No se pudo registrar el atajo {hk}.\n"
            "Es posible que otra aplicación lo esté usando.",
            "danger", 6000
        )

    def _capture_selected_text(self) -> str:
        """Copia el texto seleccionado y restaura el portapapeles original.

        Se vacía el portapapeles antes de enviar Ctrl+C: así, si no hay
        selección, el resultado es "" en lugar del contenido previo del
        portapapeles (que antes se enviaba a la IA por error). Si el
        portapapeles contiene datos no textuales (p. ej. una imagen), no se borra.
        """
        original_clip = self._safe_paste()
        preserve_non_text = not original_clip and clipboard_has_non_text()
        if not preserve_non_text:
            self._safe_copy("")

        try:
            send_copy()
            return self._wait_for_clipboard(timeout=0.35)
        finally:
            # Restaurar también cuando el portapapeles estaba vacío. Omitir
            # esta escritura dejaba la selección copiada después de usar Escriba.
            if not preserve_non_text:
                self._safe_copy(original_clip)

    def _wait_for_clipboard(self, timeout: float = 0.35, step: float = 0.05) -> str:
        """Espera (sondeando) a que el portapapeles tenga contenido."""
        for _ in range(max(1, int(timeout / step))):
            time.sleep(step)
            text = self._safe_paste()
            if text:
                return text
        return ""

    def _safe_paste(self) -> str:
        try:
            native = clipboard_paste()
            if native is not None:
                return native
            return pyperclip.paste()
        except Exception:
            return ""

    def _safe_copy(self, text: str):
        try:
            if clipboard_copy(text):
                return
            pyperclip.copy(text)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Punto de entrada
# ─────────────────────────────────────────────────────────────
def main():
    """Punto de entrada único con protección de instancia duplicada."""
    if not acquire_single_instance():
        try:
            import tkinter as tk
            from tkinter import messagebox

            tmp = tk.Tk()
            tmp.withdraw()
            messagebox.showinfo(
                APP_NAME, f"{APP_NAME} ya está ejecutándose en la bandeja del sistema."
            )
            tmp.destroy()
        except Exception:
            pass
        return
    app = EscribaApp()
    app.run()


if __name__ == "__main__":
    main()
