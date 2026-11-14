"""
Escriba - Asistente de Texto con IA para Windows y macOS v0.0.5
======================================================
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

from constants import APP_NAME, APP_VERSION
from config import ConfigManager
from ai_clients import is_ready
from history import History
from ui_common import configure_styles
from ui_windows import (
    ConfigWindow, FloatingMenu, ResultWindow, ThinkingWindow, TooltipNotification, SplashBanner,
)
from tray import TrayIconManager
from plataforma import (
    HOTKEY_LABEL, HotkeyManager, StartupManager, enable_dpi_awareness, init_app, send_copy,
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

        self.history = History()
        self.config_window = ConfigWindow(self)
        self.floating_menu = FloatingMenu(self)
        self.tooltip = TooltipNotification(self.root)
        self.tray = TrayIconManager(self)
        # El refresco del menú se hace en el hilo principal (obligatorio en macOS).
        self.history.on_change = lambda: self.schedule(self.tray.refresh)
        self.hotkey = HotkeyManager(self.root, self._on_hotkey)
        self._lock = threading.Lock()

    def run(self):
        """Inicia la app: carga config, tray, hotkey y entra al mainloop."""
        config = ConfigManager.load()
        
        # Orquestar arranque automático si está activado en config
        if config.get("autostart"):
            StartupManager.enable()
            
        self.tray.start()
        SplashBanner(self.root)
        self.root.after(500, lambda: self.hotkey.start(config.get("hotkey")))
        # Primer arranque: sin proveedor configurado, guiar al usuario a Configuración.
        if not is_ready():
            self.root.after(1800, lambda: self.config_window.show(welcome=True))
        self.root.after(3500, self._maybe_check_updates)
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.mainloop()

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
        if can_self_update():
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

    def reload_hotkey(self, hotkey: str | None = None):
        """Reinicia el listener del atajo global con la nueva combinación."""
        self.hotkey.stop()
        self.root.after(120, lambda: self.hotkey.start(hotkey))

    def open_config(self):
        self.config_window.show()

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
        self.tray.stop()
        self.floating_menu.hide()
        self.tooltip.hide()
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

    def _notify_hotkey_error(self):
        hk = ConfigManager.get("hotkey") or HOTKEY_LABEL
        self.tooltip.show(
            f"❌ Error: No se pudo registrar el atajo {hk}.\n"
            "Es posible que otra aplicación lo esté usando.",
            "danger", 6000
        )

    def _capture_selected_text(self) -> str:
        """Copia el texto seleccionado y restaura el portapapeles original.

        Se vacía el portapapeles antes de enviar Ctrl+C: así, si no hay
        selección, el resultado es "" en lugar del contenido previo del
        portapapeles (que antes se enviaba a la IA por error).
        """
        original_clip = self._safe_paste()
        self._safe_copy("")

        try:
            send_copy()
            return self._wait_for_clipboard(timeout=0.35)
        finally:
            # Restaurar también cuando el portapapeles estaba vacío. Omitir
            # esta escritura dejaba la selección copiada después de usar Escriba.
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
            return pyperclip.paste()
        except Exception:
            return ""

    def _safe_copy(self, text: str):
        try:
            pyperclip.copy(text)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Punto de entrada
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = EscribaApp()
    app.run()
