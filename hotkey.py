"""
Escriba — Hotkey global y helpers de teclado.
"""

import time
import threading
import ctypes
import ctypes.wintypes

import keyboard


# ─────────────────────────────────────────────────────────────
# Helpers de teclado (API nativa Windows)
# ─────────────────────────────────────────────────────────────
_KEYEVENTF_KEYUP = 0x0002


def _release_modifiers():
    """Suelta Win y Alt via keybd_event (API nativa Windows).
    Más fiable que keyboard.release() porque no pasa por el hook de la librería.
    """
    for virtual_key in (0x5B, 0x5C, 0x12):  # VK_LWIN, VK_RWIN, VK_MENU (Alt)
        ctypes.windll.user32.keybd_event(virtual_key, 0, _KEYEVENTF_KEYUP, 0)


def send_ctrl_c():
    """Suelta los modificadores del hotkey y envía Ctrl+C limpio."""
    _release_modifiers()
    time.sleep(0.08)
    keyboard.send('ctrl+c')


def send_ctrl_v():
    """Envía Ctrl+V."""
    keyboard.send('ctrl+v')


# ─────────────────────────────────────────────────────────────
# Hotkey Manager — RegisterHotKey (Win API)
# ─────────────────────────────────────────────────────────────
_MOD_ALT     = 0x0001
_MOD_WIN     = 0x0008
_VK_E        = 0x45
_WM_HOTKEY   = 0x0312
_WM_QUIT     = 0x0012
_HOTKEY_ID   = 1


class HotkeyManager:
    """
    Registra Win+Alt+E usando RegisterHotKey (Windows API).
    Más fiable que la librería `keyboard` para combinaciones con la tecla Win.
    """

    def __init__(self, root, callback):
        self.root      = root
        self.callback  = callback
        self._thread   = None
        self._tid      = None  # thread id para PostThreadMessage

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        ok = ctypes.windll.user32.RegisterHotKey(None, _HOTKEY_ID,
                                                  _MOD_WIN | _MOD_ALT, _VK_E)
        if not ok:
            # Notificar error de registro (ej. puerto ocupado o combinación en uso)
            if self.callback:
                self.root.after(0, lambda: self.callback(error=True))
            return

        msg = ctypes.wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                _release_modifiers()
                threading.Thread(target=self.callback, daemon=True).start()
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)

    def stop(self):
        if self._tid:
            ctypes.windll.user32.PostThreadMessageW(self._tid, _WM_QUIT, 0, 0)
            self._tid = None
