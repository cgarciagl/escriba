"""
Escriba — Capa de plataforma.

Expone una interfaz única para todo lo que depende del sistema operativo; el
resto de la app importa desde aquí y no sabe si corre en Windows o en macOS.

    HotkeyManager(root, callback)   atajo global (start/stop)
    send_copy() / send_paste()      simular copiar/pegar en la app activa
    get_foreground_window()         recordar la ventana/app de origen
    activate_window(handle)         devolverle el foco antes de pegar
    init_app() / bring_app_to_front()
    StartupManager                  inicio automático (is_enabled/enable/disable)
    HOTKEY_LABEL, PRIMARY_MODIFIER_TK, SECRET_BACKEND
"""

from __future__ import annotations

import sys
import time

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

if IS_MAC:
    from macos import (  # noqa: F401
        HOTKEY_LABEL,
        HotkeyManager,
        StartupManager,
        activate_window,
        bring_app_to_front,
        get_foreground_window,
        init_app,
        send_copy,
        send_paste,
    )

    PRIMARY_MODIFIER_TK = "Command"
    SECRET_BACKEND = "keychain"
else:
    import ctypes

    from hotkey import HotkeyManager  # noqa: F401
    from hotkey import send_ctrl_c as send_copy  # noqa: F401
    from hotkey import send_ctrl_v as send_paste  # noqa: F401
    from startup import StartupManager  # noqa: F401

    HOTKEY_LABEL = "Win + Alt + E"
    PRIMARY_MODIFIER_TK = "Control"
    SECRET_BACKEND = "dpapi" if IS_WINDOWS else "plain"

    def init_app():
        pass

    def bring_app_to_front():
        pass

    def get_foreground_window():
        return ctypes.windll.user32.GetForegroundWindow()

    def activate_window(handle) -> None:
        """Devuelve el foco a la ventana de origen (AttachThreadInput + SetForegroundWindow)."""
        if not handle:
            return
        user32 = ctypes.windll.user32
        fore_tid = user32.GetWindowThreadProcessId(handle, None)
        cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
        attach = bool(fore_tid and fore_tid != cur_tid)
        if attach:
            user32.AttachThreadInput(cur_tid, fore_tid, True)
        user32.SetForegroundWindow(handle)
        user32.BringWindowToTop(handle)
        if attach:
            user32.AttachThreadInput(cur_tid, fore_tid, False)
        time.sleep(0.25)


def tk_shortcut(windows_key: str, mac_key: str | None = None) -> str:
    """Secuencia Tk con el modificador principal: Control en Windows, Command en macOS."""
    return f"<{PRIMARY_MODIFIER_TK}-{mac_key if (IS_MAC and mac_key) else windows_key}>"


def shortcut_label(text: str) -> str:
    """Convierte "Ctrl+Enter" en "⌘↩" en macOS; en Windows lo deja igual."""
    if not IS_MAC:
        return text
    symbols = {"ctrl": "⌘", "cmd": "⌘", "command": "⌘", "alt": "⌥", "shift": "⇧",
               "enter": "↩", "espacio": "Espacio"}
    return "".join(symbols.get(p.strip().lower(), p.strip().upper()) for p in text.split("+"))
