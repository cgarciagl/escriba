"""
Escriba — Implementación para Linux (X11) de las funciones dependientes del sistema.

Equivalencias con Windows / macOS:
  RegisterHotKey            → pynput.GlobalHotKeys (Ctrl+Alt+E por defecto)
  keybd_event Ctrl+C/V      → pynput.keyboard.Controller Ctrl+C/V
  GetForegroundWindow       → xdotool getactivewindow
  SetForegroundWindow       → xdotool windowactivate --sync
  HKCU\\...\\Run              → Archivo .desktop en ~/.config/autostart/escriba.desktop

Las dependencias de pynput y las llamadas a xdotool se ejecutan de forma
diferida para que este módulo pueda importarse y probarse sin servidor X.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time

from constants import APP_NAME

HOTKEY_PYNPUT = "<ctrl>+<alt>+e"
HOTKEY_LABEL = "Ctrl + Alt + E"


# ─────────────────────────────────────────────────────────────
# Arranque / Foco de la app
# ─────────────────────────────────────────────────────────────
def init_app():
    """No requiere inicialización especial en Linux."""
    pass


def bring_app_to_front():
    """Tk gestiona el foco de sus propias ventanas en X11."""
    pass


# ─────────────────────────────────────────────────────────────
# Teclado: Ctrl+C / Ctrl+V
# ─────────────────────────────────────────────────────────────
def _release_modifiers(controller, keyboard_mod) -> None:
    """Suelta modificadores que el usuario pudiera seguir manteniendo del atajo."""
    for attr in (
        "alt", "alt_l", "alt_r",
        "ctrl", "ctrl_l", "ctrl_r",
        "shift", "shift_l", "shift_r",
        "cmd", "cmd_l", "cmd_r",
    ):
        key = getattr(keyboard_mod.Key, attr, None)
        if key is not None:
            try:
                controller.release(key)
            except Exception:
                pass


def _send_ctrl_combo(char: str) -> None:
    from pynput import keyboard

    ctrl = keyboard.Controller()
    _release_modifiers(ctrl, keyboard)
    time.sleep(0.02)
    with ctrl.pressed(keyboard.Key.ctrl):
        ctrl.press(char)
        time.sleep(0.01)
        ctrl.release(char)


def send_copy():
    time.sleep(0.05)
    _send_ctrl_combo("c")


def send_paste():
    _send_ctrl_combo("v")


# ─────────────────────────────────────────────────────────────
# Ventana en primer plano (X11 vía xdotool)
# ─────────────────────────────────────────────────────────────
def get_foreground_window():
    """Devuelve el ID de ventana X11 activa (str) o None si no está disponible."""
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=2,
        )
        win_id = result.stdout.strip()
        return win_id if result.returncode == 0 and win_id else None
    except Exception:
        return None


def activate_window(handle) -> None:
    """Devuelve el foco a la ventana de origen antes de pegar."""
    if not handle:
        return
    try:
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", str(handle)],
            capture_output=True, text=True, timeout=2,
        )
    except Exception:
        pass
    time.sleep(0.20)


# ─────────────────────────────────────────────────────────────
# Atajo global
# ─────────────────────────────────────────────────────────────
def _to_pynput(hotkey: str | None) -> str:
    """Convierte 'Ctrl+Alt+E' → '<ctrl>+<alt>+e'. Si no es válido, usa el predeterminado."""
    if not hotkey or not isinstance(hotkey, str):
        return HOTKEY_PYNPUT
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if len(parts) < 2:
        return HOTKEY_PYNPUT
    mod_map = {
        "ctrl": "<ctrl>",
        "control": "<ctrl>",
        "alt": "<alt>",
        "option": "<alt>",
        "shift": "<shift>",
        "win": "<cmd>",
        "super": "<cmd>",
        "cmd": "<cmd>",
        "command": "<cmd>",
    }
    out = []
    for p in parts[:-1]:
        m = mod_map.get(p)
        if not m:
            return HOTKEY_PYNPUT
        out.append(m)
    key = parts[-1]
    if key in ("space", "espacio"):
        out.append("<space>")
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        out.append(f"<{key}>")
    elif len(key) == 1 and key.isalnum():
        out.append(key)
    else:
        return HOTKEY_PYNPUT
    return "+".join(out)


class HotkeyManager:
    """Registra el atajo global en X11 con pynput (por defecto Ctrl+Alt+E)."""

    def __init__(self, root, callback, hotkey: str | None = None):
        self.root = root
        self.callback = callback
        self.hotkey = hotkey
        self._listener = None

    def _fire(self):
        threading.Thread(target=self.callback, daemon=True).start()

    def start(self, hotkey: str | None = None):
        if hotkey is not None:
            self.hotkey = hotkey
        try:
            from pynput import keyboard

            combo = _to_pynput(self.hotkey)
            self._listener = keyboard.GlobalHotKeys({combo: self._fire})
            self._listener.start()
        except Exception:
            if self.callback:
                self.root.after(0, lambda: self.callback(error=True))

    def stop(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None


# ─────────────────────────────────────────────────────────────
# Inicio automático: archivo .desktop en XDG autostart
# ─────────────────────────────────────────────────────────────
class StartupManager:
    """Crea/elimina ~/.config/autostart/escriba.desktop."""

    @staticmethod
    def _autostart_dir() -> str:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        return os.path.join(base, "autostart")

    @classmethod
    def desktop_path(cls) -> str:
        return os.path.join(cls._autostart_dir(), "escriba.desktop")

    @staticmethod
    def _exec_line() -> str:
        if getattr(sys, "frozen", False):
            return shlex.quote(sys.executable)
        main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "escriba.py")
        return f"{shlex.quote(sys.executable)} {shlex.quote(main_script)}"

    @classmethod
    def is_enabled(cls) -> bool:
        return os.path.exists(cls.desktop_path())

    @classmethod
    def enable(cls):
        os.makedirs(cls._autostart_dir(), exist_ok=True)
        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            "Comment=Asistente de texto con IA\n"
            f"Exec={cls._exec_line()}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        with open(cls.desktop_path(), "w", encoding="utf-8") as f:
            f.write(content)

    @classmethod
    def disable(cls):
        try:
            os.remove(cls.desktop_path())
        except FileNotFoundError:
            pass
