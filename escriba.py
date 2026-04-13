"""
Escriba - Asistente de Texto con IA para Windows v2.1
======================================================
Hotkey: Ctrl+Shift+Space
- Registrado con `keyboard` library (suppress=True).
  Garantiza que la tecla NUNCA filtra a otras aplicaciones.

Stack: ttkbootstrap, pystray, Pillow, pyperclip, ctypes, requests
"""

import os
import time
import threading

import ttkbootstrap as tb
import pyperclip

from constants import APP_NAME
from config import ConfigManager
from ui_windows import (
    ConfigWindow, FloatingMenu, TooltipNotification, SplashBanner,
)
from tray import TrayIconManager
from hotkey import HotkeyManager, send_ctrl_c


# ─────────────────────────────────────────────────────────────
# Aplicación Principal
# ─────────────────────────────────────────────────────────────
class EscribaApp:
    """Orquestador principal: conecta hotkey, tray, y ventanas UI."""

    def __init__(self):
        self.root    = tb.Window(themename="vapor")
        self.root.title(APP_NAME)
        self.root.withdraw()

        self.config_window = ConfigWindow(self)
        self.floating_menu = FloatingMenu(self)
        self.tooltip       = TooltipNotification(self.root)
        self.tray          = TrayIconManager(self)
        self.hotkey        = HotkeyManager(self.root, self._on_hotkey)
        self._lock         = threading.Lock()

    def run(self):
        """Inicia la app: carga config, tray, hotkey y entra al mainloop."""
        ConfigManager.load()
        self.tray.start()
        SplashBanner(self.root)
        self.root.after(500, self.hotkey.start)
        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.mainloop()

    def open_config(self):
        self.config_window.show()

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

    def _on_hotkey(self):
        """Ejecutado en hilo secundario al detectar Ctrl+Shift+Space."""
        if not self._lock.acquire(blocking=False):
            return
        try:
            old_clip = ""
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass

            send_ctrl_c()
            time.sleep(0.40)

            try:
                selected = pyperclip.paste()
            except Exception:
                selected = ""

            if selected == old_clip:
                send_ctrl_c()
                time.sleep(0.35)
                try:
                    selected = pyperclip.paste()
                except Exception:
                    selected = ""

            self.root.after(0, self.floating_menu.show, selected)
        finally:
            self._lock.release()


# ─────────────────────────────────────────────────────────────
# Punto de entrada
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = EscribaApp()
    app.run()
