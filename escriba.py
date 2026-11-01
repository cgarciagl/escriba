"""
Escriba - Asistente de Texto con IA para Windows v1.0.0
======================================================
Hotkey: Win+Alt+E
- Registrado con la API de Windows `RegisterHotKey` (ver hotkey.py), por lo que
  la combinación no llega a otras aplicaciones.

Stack: ttkbootstrap, pystray, Pillow, pyperclip, ctypes, requests
"""

import os
import time
import threading

import ttkbootstrap as tb
import pyperclip

from constants import APP_NAME
from config import ConfigManager
from history import History
from ui_windows import (
    ConfigWindow, FloatingMenu, ResultWindow, TooltipNotification, SplashBanner,
)
from tray import TrayIconManager
from hotkey import HotkeyManager, send_ctrl_c
from startup import StartupManager


# ─────────────────────────────────────────────────────────────
# Aplicación Principal
# ─────────────────────────────────────────────────────────────
class EscribaApp:
    """Orquestador principal: conecta hotkey, tray, y ventanas UI."""

    def __init__(self):
        self.root = tb.Window(themename="vapor")
        self.root.title(APP_NAME)
        self.root.withdraw()

        self.history = History()
        self.config_window = ConfigWindow(self)
        self.floating_menu = FloatingMenu(self)
        self.tooltip = TooltipNotification(self.root)
        self.tray = TrayIconManager(self)
        self.history.on_change = self.tray.refresh
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
        self.root.after(500, self.hotkey.start)
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.mainloop()

    def open_config(self):
        self.config_window.show()

    def open_history_entry(self, entry):
        """Reabre una respuesta del historial (sin ventana de origen: no se puede sustituir)."""
        ResultWindow(
            self, entry.result, None,
            prompt=entry.prompt, selected_text=entry.selected_text,
            provider=entry.provider, label=entry.label,
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
        self.tooltip.show(
            "❌ Error: No se pudo registrar el atajo Win+Alt+E.\n"
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

        send_ctrl_c()
        selected = self._wait_for_clipboard()
        if not selected:
            send_ctrl_c()
            selected = self._wait_for_clipboard()

        if original_clip:
            self._safe_copy(original_clip)
        return selected

    def _wait_for_clipboard(self, timeout: float = 0.6, step: float = 0.05) -> str:
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
