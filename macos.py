"""
Escriba — Implementación para macOS de las funciones dependientes del sistema.

Equivalencias con Windows:
  RegisterHotKey            → pynput.GlobalHotKeys (Ctrl+Cmd+E)
  keybd_event Ctrl+C/V      → CGEvent Cmd+C/V con banderas explícitas
  GetForegroundWindow       → NSWorkspace.frontmostApplication
  SetForegroundWindow       → NSRunningApplication.activateWithOptions_
  HKCU\\...\\Run              → LaunchAgent en ~/Library/LaunchAgents
  DPAPI                     → Llavero de macOS (comando `security`)

Permisos: macOS pedirá **Accesibilidad** (para enviar Cmd+C/V) y
**Monitorización de entrada** (para el atajo global). Se conceden en
Ajustes del Sistema → Privacidad y seguridad.

Las dependencias de PyObjC/pynput se importan de forma diferida para que este
módulo pueda importarse (y probarse) en cualquier sistema.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import threading
import time

from constants import APP_NAME

HOTKEY_PYNPUT = "<ctrl>+<cmd>+e"
HOTKEY_LABEL = "⌃ + ⌘ + E"

# Códigos de tecla virtuales (distribución ANSI) y banderas de Quartz
_KVK_ANSI_C = 8
_KVK_ANSI_V = 9
_FLAG_COMMAND = 1 << 20  # kCGEventFlagMaskCommand


# ─────────────────────────────────────────────────────────────
# Arranque de la app
# ─────────────────────────────────────────────────────────────
def init_app():
    """Oculta el ícono del Dock (app de barra de menús, como LSUIElement)."""
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass


def bring_app_to_front():
    """Activa Escriba para que sus ventanas reciban el teclado."""
    try:
        from AppKit import NSApplication

        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# Teclado: Cmd+C / Cmd+V
# ─────────────────────────────────────────────────────────────
def _post_command_key(keycode: int):
    """Envía Cmd+<tecla> con banderas explícitas.

    Fijar las banderas del evento hace que se ignoren los modificadores que el
    usuario aún tenga presionados (Ctrl del atajo global), así que no hace falta
    "soltarlos" como en Windows.
    """
    import Quartz

    for key_down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, keycode, key_down)
        Quartz.CGEventSetFlags(event, _FLAG_COMMAND)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.01)


def send_copy():
    time.sleep(0.05)
    _post_command_key(_KVK_ANSI_C)


def send_paste():
    _post_command_key(_KVK_ANSI_V)


# ─────────────────────────────────────────────────────────────
# Aplicación en primer plano
# ─────────────────────────────────────────────────────────────
def get_foreground_window():
    """Devuelve la app activa (NSRunningApplication) o None."""
    try:
        from AppKit import NSWorkspace

        return NSWorkspace.sharedWorkspace().frontmostApplication()
    except Exception:
        return None


def activate_window(handle) -> None:
    """Vuelve a poner en primer plano la app donde estaba el texto."""
    if handle is None:
        return
    from AppKit import NSApplicationActivateIgnoringOtherApps

    handle.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
    time.sleep(0.25)


# ─────────────────────────────────────────────────────────────
# Atajo global
# ─────────────────────────────────────────────────────────────
def _to_pynput(hotkey: str | None) -> str:
    """Convierte 'Ctrl+Cmd+E' → '<ctrl>+<cmd>+e'. Si no es válido, usa el predeterminado."""
    if not hotkey or not isinstance(hotkey, str):
        return HOTKEY_PYNPUT
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if len(parts) < 2:
        return HOTKEY_PYNPUT
    mod_map = {"ctrl": "<ctrl>", "control": "<ctrl>", "cmd": "<cmd>", "command": "<cmd>",
               "alt": "<alt>", "option": "<alt>", "shift": "<shift>"}
    out = []
    for p in parts[:-1]:
        m = mod_map.get(p)
        if not m:
            return HOTKEY_PYNPUT
        out.append(m)
    key = parts[-1]
    if key in ("space", "espacio"):
        out.append("<space>")
    elif len(key) == 1 and key.isalnum():
        out.append(key)
    else:
        return HOTKEY_PYNPUT
    return "+".join(out)


class HotkeyManager:
    """Registra el atajo global con pynput (por defecto Ctrl+Cmd+E)."""

    def __init__(self, root, callback, hotkey: str | None = None):
        self.root = root
        self.callback = callback
        self.hotkey = hotkey
        self._listener = None

    def _fire(self):
        # Igual que en Windows: el trabajo va en otro hilo para no bloquear el listener.
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
# Inicio automático: LaunchAgent
# ─────────────────────────────────────────────────────────────
LAUNCH_AGENT_LABEL = "com.cgarciagl.escriba"
LAUNCH_AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")


class StartupManager:
    """Crea/elimina ~/Library/LaunchAgents/com.cgarciagl.escriba.plist."""

    @staticmethod
    def plist_path() -> str:
        return os.path.join(LAUNCH_AGENTS_DIR, f"{LAUNCH_AGENT_LABEL}.plist")

    @staticmethod
    def _program_arguments() -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable]
        main_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "escriba.py")
        return [sys.executable, main_script]

    @classmethod
    def is_enabled(cls) -> bool:
        return os.path.exists(cls.plist_path())

    @classmethod
    def enable(cls):
        os.makedirs(LAUNCH_AGENTS_DIR, exist_ok=True)
        data = {
            "Label": LAUNCH_AGENT_LABEL,
            "ProgramArguments": cls._program_arguments(),
            "RunAtLoad": True,
            "ProcessType": "Interactive",
        }
        with open(cls.plist_path(), "wb") as f:
            plistlib.dump(data, f)

    @classmethod
    def disable(cls):
        try:
            os.remove(cls.plist_path())
        except FileNotFoundError:
            pass


# ─────────────────────────────────────────────────────────────
# Secretos: Llavero de macOS
# ─────────────────────────────────────────────────────────────
KEYCHAIN_SERVICE = APP_NAME


def keychain_get(name: str) -> str:
    """Lee un secreto del llavero. Devuelve "" si no existe."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name, "-w"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def keychain_set(name: str, value: str):
    """Guarda (o borra, si value está vacío) un secreto en el llavero."""
    if not value:
        subprocess.run(
            ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", name],
            capture_output=True, text=True,
        )
        return
    # Pasar la clave por stdin (security -i) evita exponerla en la lista de procesos (ps).
    def _q(arg: str) -> str:
        return '"' + arg.replace('\\', '\\\\').replace('"', '\\"') + '"'

    cmd = f"add-generic-password -U -s {_q(KEYCHAIN_SERVICE)} -a {_q(name)} -w {_q(value)}\n"
    result = subprocess.run(
        ["security", "-i"],
        input=cmd, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise OSError(f"Llavero: {result.stderr.strip() or 'no se pudo guardar el secreto'}")
