"""
Escriba — Hotkey global y helpers de teclado.
"""

import time
import threading
import ctypes

import keyboard


# ─────────────────────────────────────────────────────────────
# Helpers de teclado (API nativa Windows)
# ─────────────────────────────────────────────────────────────
_KEYEVENTF_KEYUP = 0x0002


def _release_modifiers():
    """Suelta Ctrl, Shift y Space via keybd_event (API nativa Windows).
    Más fiable que keyboard.release() porque no pasa por el hook de la librería.
    """
    for vk in (0x11, 0x10, 0x20):  # VK_CONTROL, VK_SHIFT, VK_SPACE
        ctypes.windll.user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


def send_ctrl_c():
    """Suelta los modificadores del hotkey y envía Ctrl+C limpio."""
    _release_modifiers()
    time.sleep(0.08)
    keyboard.send('ctrl+c')


def send_ctrl_v():
    """Envía Ctrl+V."""
    keyboard.send('ctrl+v')


# ─────────────────────────────────────────────────────────────
# Hotkey Manager — keyboard library
# ─────────────────────────────────────────────────────────────
class HotkeyManager:
    """
    Usa `keyboard` para registrar Ctrl+Shift+Space globalmente.
    suppress=True evita que la combinación llegue a otras aplicaciones.
    """

    def __init__(self, root, callback):
        self.root     = root
        self.callback = callback
        self._hook    = None

    def start(self):
        def _on_trigger():
            _release_modifiers()
            threading.Thread(target=self.callback, daemon=True).start()

        self._hook = keyboard.add_hotkey(
            'ctrl+shift+space',
            _on_trigger,
            suppress=True,
        )

    def stop(self):
        if self._hook:
            try:
                keyboard.remove_hotkey(self._hook)
            except Exception:
                pass
            self._hook = None
