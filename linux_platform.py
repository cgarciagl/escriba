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

import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time

from constants import APP_NAME

HOTKEY_PYNPUT = "<ctrl>+<alt>+e"
HOTKEY_LABEL = "Ctrl + Alt + E"


def is_wayland() -> bool:
    """Indica si la sesión actual de Linux corre bajo Wayland."""
    session = (os.environ.get("XDG_SESSION_TYPE") or "").strip().lower()
    if session == "wayland":
        return True
    return bool(os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"))


def has_wayland_tools() -> tuple[bool, bool]:
    """Devuelve (wl_copy_disponible, wtype_disponible) para entornos Wayland."""
    return bool(shutil.which("wl-copy")), bool(shutil.which("wtype"))


def wl_copy(text: str, html_text: str | None = None) -> bool:
    """Copia al portapapeles usando wl-copy en Wayland; devuelve True si tuvo éxito."""
    if not is_wayland() or not shutil.which("wl-copy"):
        return False
    try:
        cmd = ["wl-copy"]
        payload = text or ""
        if html_text is not None:
            cmd.extend(["--type", "text/html"])
            payload = html_text
        subprocess.run(cmd, input=payload, text=True, capture_output=True, timeout=2, check=True)
        return True
    except Exception:
        return False


def wl_paste() -> str | None:
    """Lee el portapapeles usando wl-paste en Wayland; devuelve None si no aplica."""
    if not is_wayland() or not shutil.which("wl-paste"):
        return None
    try:
        res = subprocess.run(
            ["wl-paste", "--no-newline"],
            capture_output=True, text=True, timeout=2,
        )
        return res.stdout if res.returncode == 0 else ""
    except Exception:
        return None


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
    if is_wayland() and shutil.which("wtype"):
        subprocess.run(
            ["wtype", "-M", "ctrl", "-k", char, "-m", "ctrl"],
            capture_output=True, timeout=2,
        )
        return
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
# Ventana en primer plano (X11 vía xdotool; Wayland en Hyprland/Sway)
# ─────────────────────────────────────────────────────────────
def _sway_find_focused(node: dict) -> dict | None:
    if node.get("focused"):
        return node
    for key in ("nodes", "floating_nodes"):
        for child in node.get(key) or ():
            found = _sway_find_focused(child)
            if found is not None:
                return found
    return None


def _wayland_active_window() -> tuple[str, str, str] | None:
    """Devuelve (compositor, id_ventana, app_name) en Hyprland o Sway, o None."""
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hyprctl"):
        try:
            res = subprocess.run(
                ["hyprctl", "activewindow", "-j"],
                capture_output=True, text=True, timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                addr = str(data.get("address") or "").strip()
                cls = str(data.get("class") or data.get("initialClass") or "").strip().lower()
                if addr or cls:
                    return ("hyprland", addr, cls)
        except Exception:
            pass
    if os.environ.get("SWAYSOCK") and shutil.which("swaymsg"):
        try:
            res = subprocess.run(
                ["swaymsg", "-t", "get_tree"],
                capture_output=True, text=True, timeout=2,
            )
            if res.returncode == 0 and res.stdout.strip():
                focused = _sway_find_focused(json.loads(res.stdout))
                if focused:
                    con_id = str(focused.get("id") or "").strip()
                    props = focused.get("window_properties") or {}
                    app_id = str(focused.get("app_id") or props.get("class") or "").strip().lower()
                    if con_id or app_id:
                        return ("sway", con_id, app_id)
        except Exception:
            pass
    return None


def get_foreground_window():
    """Devuelve el identificador de la ventana activa (X11 o Wayland) o None."""
    if is_wayland():
        wl = _wayland_active_window()
        if wl and wl[1]:
            return f"{wl[0]}:{wl[1]}"
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=2,
        )
        win_id = result.stdout.strip()
        return win_id if result.returncode == 0 and win_id else None
    except Exception:
        return None


def get_foreground_app_name(handle=None) -> str:
    """Devuelve la clase/nombre de la ventana activa en minúsculas o ''."""
    if is_wayland():
        wl = _wayland_active_window()
        if wl and wl[2]:
            return wl[2]
    target = handle or get_foreground_window()
    if not target or str(target).startswith(("hyprland:", "sway:")):
        return ""
    try:
        result = subprocess.run(
            ["xdotool", "getwindowclassname", str(target)],
            capture_output=True, text=True, timeout=2,
        )
        name = (result.stdout or "").strip().lower()
        return name if result.returncode == 0 else ""
    except Exception:
        return ""


def activate_window(handle) -> None:
    """Devuelve el foco a la ventana de origen antes de pegar."""
    if not handle:
        return
    raw = str(handle)
    try:
        if raw.startswith("hyprland:") and shutil.which("hyprctl"):
            addr = raw.split(":", 1)[1]
            subprocess.run(
                ["hyprctl", "dispatch", "focuswindow", f"address:{addr}"],
                capture_output=True, text=True, timeout=2,
            )
        elif raw.startswith("sway:") and shutil.which("swaymsg"):
            con_id = raw.split(":", 1)[1]
            subprocess.run(
                ["swaymsg", f"[con_id={con_id}]", "focus"],
                capture_output=True, text=True, timeout=2,
            )
        else:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", raw],
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

    def __init__(self, root, callback, hotkey: str | None = None, hotkey_id: int = 1):
        self.root = root
        self.callback = callback
        self.hotkey = hotkey
        self._hotkey_id = hotkey_id
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
