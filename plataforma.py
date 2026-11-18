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

import html
import os
import re
import sys
import time

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

if IS_MAC:
    from macos import (  # noqa: F401
        HOTKEY_LABEL,
        HotkeyManager,
        StartupManager,
        activate_window,
        bring_app_to_front,
        get_foreground_app_name,
        get_foreground_window,
        init_app,
        send_copy,
        send_paste,
    )

    PRIMARY_MODIFIER_TK = "Command"
    SECRET_BACKEND = "keychain"

    def enable_dpi_awareness():
        pass  # macOS gestiona Retina por su cuenta

    def monitor_workarea(x: int, y: int):
        return None  # se usa el tamaño de pantalla que reporta Tk

    def is_wayland() -> bool:
        return False
elif IS_WINDOWS:
    import ctypes

    from hotkey import HotkeyManager  # noqa: F401
    from hotkey import send_ctrl_c as send_copy  # noqa: F401
    from hotkey import send_ctrl_v as send_paste  # noqa: F401
    from startup import StartupManager  # noqa: F401

    HOTKEY_LABEL = "Win + Alt + E"
    PRIMARY_MODIFIER_TK = "Control"
    SECRET_BACKEND = "dpapi"

    def init_app():
        pass

    def enable_dpi_awareness():
        """Declara soporte de DPI para que el texto no se vea borroso con escalado.

        Debe llamarse ANTES de crear la ventana raíz de Tk.
        """
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor (Windows 8.1+)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()     # Sistema (Vista+)
            except Exception:
                pass

    def monitor_workarea(x: int, y: int):
        """Área de trabajo (sin barra de tareas) del monitor que contiene (x, y)."""
        try:
            import ctypes.wintypes as wt

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                            ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]

            user32 = ctypes.windll.user32
            monitor = user32.MonitorFromPoint(wt.POINT(int(x), int(y)), 2)  # MONITOR_DEFAULTTONEAREST
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return None
            r = info.rcWork
            return (r.left, r.top, r.right, r.bottom)
        except Exception:
            return None

    def bring_app_to_front():
        pass

    def get_foreground_window():
        return ctypes.windll.user32.GetForegroundWindow()

    def get_foreground_app_name(handle=None) -> str:
        """Devuelve el nombre del ejecutable (sin .exe, minúsculas) de la ventana activa."""
        try:
            import ctypes.wintypes as wt

            hwnd = handle or get_foreground_window()
            if not hwnd:
                return ""
            pid = wt.DWORD(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return ""
            proc = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not proc:
                return ""
            try:
                size = wt.DWORD(512)
                buf = ctypes.create_unicode_buffer(512)
                if ctypes.windll.kernel32.QueryFullProcessImageNameW(proc, 0, buf, ctypes.byref(size)):
                    base = os.path.basename(buf.value)
                    return os.path.splitext(base)[0].strip().lower()
            finally:
                ctypes.windll.kernel32.CloseHandle(proc)
        except Exception:
            pass
        return ""

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

    def clipboard_has_non_text() -> bool:
        """Indica si el portapapeles tiene contenido no textual (ej. imagen o archivo)."""
        try:
            user32 = ctypes.windll.user32
            if user32.CountClipboardFormats() <= 0:
                return False
            return not (
                user32.IsClipboardFormatAvailable(13)  # CF_UNICODETEXT
                or user32.IsClipboardFormatAvailable(1)  # CF_TEXT
            )
        except Exception:
            return False

    def is_wayland() -> bool:
        return False
else:
    from linux_platform import (  # noqa: F401
        HOTKEY_LABEL,
        HotkeyManager,
        StartupManager,
        activate_window,
        bring_app_to_front,
        get_foreground_app_name,
        get_foreground_window,
        init_app,
        is_wayland,
        send_copy,
        send_paste,
    )

    PRIMARY_MODIFIER_TK = "Control"
    SECRET_BACKEND = "plain"

    def enable_dpi_awareness():
        pass  # X11 / Tk gestiona el escalado por su cuenta

    def monitor_workarea(x: int, y: int):
        return None  # se usa el tamaño de pantalla que reporta Tk


if not IS_WINDOWS:
    def clipboard_has_non_text() -> bool:
        """Indica si el portapapeles contiene datos no textuales."""
        return False


def clamp_to_area(x: int, y: int, width: int, height: int, area) -> tuple[int, int]:
    """Ajusta (x, y) para que una ventana de width×height quepa dentro de area.

    area = (izquierda, arriba, derecha, abajo). Si la ventana no cabe a la
    derecha/abajo del punto, se desplaza hacia dentro del área.
    """
    left, top, right, bottom = area
    x = max(left, min(x, right - width))
    y = max(top, min(y, bottom - height))
    return int(x), int(y)


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


def format_hotkey_label(hotkey: str | None) -> str:
    """Formatea un atajo global como 'Win+Alt+E' para mostrarlo en la UI."""
    raw = (hotkey or "").strip()
    if not raw:
        return HOTKEY_LABEL
    parts = [p.strip() for p in raw.split("+") if p.strip()]
    if not parts:
        return HOTKEY_LABEL
    if IS_MAC:
        mac_map = {
            "ctrl": "⌃", "control": "⌃",
            "cmd": "⌘", "command": "⌘",
            "alt": "⌥", "option": "⌥",
            "shift": "⇧",
            "space": "Espacio", "espacio": "Espacio",
        }
        return " + ".join(mac_map.get(p.lower(), p.upper()) for p in parts)
    win_map = {
        "ctrl": "Ctrl", "control": "Ctrl",
        "alt": "Alt", "option": "Alt",
        "shift": "Shift",
        "win": "Win", "super": "Super" if IS_LINUX else "Win",
        "space": "Espacio", "espacio": "Espacio",
    }
    return " + ".join(win_map.get(p.lower(), p.upper() if len(p) == 1 else p.capitalize()) for p in parts)


def active_hotkey_label() -> str:
    """Devuelve el atajo global configurado formateado para la plataforma actual."""
    try:
        from config import ConfigManager

        return format_hotkey_label(ConfigManager.get("hotkey"))
    except Exception:
        return HOTKEY_LABEL


_INSTANCE_LOCK = None


def acquire_single_instance(name: str = "Escriba") -> bool:
    """Asegura una única instancia en ejecución. Devuelve False si ya hay otra activa."""
    global _INSTANCE_LOCK
    if _INSTANCE_LOCK is not None:
        return True

    if IS_WINDOWS:
        try:
            import ctypes as _ctypes

            kernel32 = _ctypes.windll.kernel32
            handle = kernel32.CreateMutexW(None, False, f"Local\\{name}_SingleInstance")
            last_err = kernel32.GetLastError()
            if last_err == 183:  # ERROR_ALREADY_EXISTS
                if handle:
                    kernel32.CloseHandle(handle)
                return False
            _INSTANCE_LOCK = handle
            return True
        except Exception:
            return True

    try:
        import fcntl
        import tempfile

        lock_path = f"{tempfile.gettempdir()}/{name.lower()}.lock"
        fh = open(lock_path, "a+", encoding="utf-8")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        _INSTANCE_LOCK = fh
        return True
    except Exception:
        return True


def release_single_instance():
    """Libera el bloqueo de instancia única al cerrar la app."""
    global _INSTANCE_LOCK
    if _INSTANCE_LOCK is None:
        return
    try:
        if IS_WINDOWS:
            import ctypes as _ctypes

            _ctypes.windll.kernel32.CloseHandle(_INSTANCE_LOCK)
        else:
            import fcntl

            fcntl.flock(_INSTANCE_LOCK.fileno(), fcntl.LOCK_UN)
            _INSTANCE_LOCK.close()
    except Exception:
        pass
    finally:
        _INSTANCE_LOCK = None


def _inline_md_to_html(line: str) -> str:
    escaped = html.escape(line)
    escaped = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def markdown_to_html(text: str) -> str:
    """Convierte Markdown básico (encabezados, listas, negritas, código) a HTML limpio."""
    lines = (text or "").splitlines()
    out: list[str] = []
    in_code = False
    list_tag: str | None = None

    def _close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    for line in lines:
        if line.strip().startswith("```"):
            _close_list()
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line) + "\n")
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            _close_list()
            lvl = len(heading.group(1))
            out.append(f"<h{lvl}>{_inline_md_to_html(heading.group(2).strip())}</h{lvl}>")
            continue

        ul = re.match(r"^\s*[-*•]\s+(.+)$", line)
        if ul:
            if list_tag != "ul":
                _close_list()
                list_tag = "ul"
                out.append("<ul>")
            out.append(f"<li>{_inline_md_to_html(ul.group(1))}</li>")
            continue

        ol = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if ol:
            if list_tag != "ol":
                _close_list()
                list_tag = "ol"
                out.append("<ol>")
            out.append(f"<li>{_inline_md_to_html(ol.group(1))}</li>")
            continue

        _close_list()
        if line.strip():
            out.append(f"<p>{_inline_md_to_html(line)}</p>")

    _close_list()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def _build_win_cf_html(fragment: str) -> bytes:
    header_tpl = (
        "Version:0.9\r\n"
        "StartHTML:{start_html:08d}\r\n"
        "EndHTML:{end_html:08d}\r\n"
        "StartFragment:{start_frag:08d}\r\n"
        "EndFragment:{end_frag:08d}\r\n"
    )
    prefix = "<html>\r\n<body>\r\n<!--StartFragment-->"
    suffix = "<!--EndFragment-->\r\n</body>\r\n</html>"
    frag_bytes = fragment.encode("utf-8")
    dummy = header_tpl.format(start_html=0, end_html=0, start_frag=0, end_frag=0).encode("utf-8")
    start_html = len(dummy)
    start_frag = start_html + len(prefix.encode("utf-8"))
    end_frag = start_frag + len(frag_bytes)
    end_html = end_frag + len(suffix.encode("utf-8"))
    header = header_tpl.format(
        start_html=start_html, end_html=end_html,
        start_frag=start_frag, end_frag=end_frag,
    ).encode("utf-8")
    return header + prefix.encode("utf-8") + frag_bytes + suffix.encode("utf-8") + b"\x00"


def copy_rich_text(plain_text: str, html_text: str | None = None) -> bool:
    """Copia texto plano y HTML simultáneamente al portapapeles; vuelve a texto plano si falla."""
    fragment = markdown_to_html(plain_text) if html_text is None else html_text
    if IS_WINDOWS:
        try:
            import ctypes as _ctypes

            user32 = _ctypes.windll.user32
            kernel32 = _ctypes.windll.kernel32
            html_bytes = _build_win_cf_html(fragment)
            uni_bytes = (plain_text or "").encode("utf-16-le") + b"\x00\x00"
            html_fmt = user32.RegisterClipboardFormatW("HTML Format")

            def _alloc(raw: bytes):
                h = kernel32.GlobalAlloc(0x0002, len(raw))
                if not h:
                    return None
                ptr = kernel32.GlobalLock(h)
                if not ptr:
                    kernel32.GlobalFree(h)
                    return None
                _ctypes.memmove(ptr, raw, len(raw))
                kernel32.GlobalUnlock(h)
                return h

            if user32.OpenClipboard(None):
                try:
                    user32.EmptyClipboard()
                    h_uni = _alloc(uni_bytes)
                    if h_uni:
                        user32.SetClipboardData(13, h_uni)
                    if html_fmt:
                        h_html = _alloc(html_bytes)
                        if h_html:
                            user32.SetClipboardData(html_fmt, h_html)
                    return True
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass
    elif IS_MAC:
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeHTML, NSPasteboardTypeString

            pb = NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.declareTypes_owner_([NSPasteboardTypeHTML, NSPasteboardTypeString], None)
            pb.setString_forType_(fragment, NSPasteboardTypeHTML)
            pb.setString_forType_(plain_text, NSPasteboardTypeString)
            return True
        except Exception:
            pass

    import pyperclip
    pyperclip.copy(plain_text)
    return False

