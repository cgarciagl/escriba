"""
Escriba — Icono del System Tray.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import pystray
from PIL import Image, ImageDraw

from config import tr
from constants import APP_NAME, APP_VERSION, BASE_DIR
from plataforma import IS_MAC, active_hotkey_label

if TYPE_CHECKING:
    from escriba import EscribaApp


class TrayIconManager:
    """Crea y gestiona el ícono en la bandeja del sistema."""

    def __init__(self, app: EscribaApp):
        self.app = app
        self.icon = None

    @staticmethod
    def _build_image() -> Image.Image:
        for name in ("escriba_logo.png", "escriba.ico"):
            path = os.path.join(BASE_DIR, name)
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    return img.convert("RGBA").resize((64, 64), Image.LANCZOS)
                except Exception:
                    pass
        # Fallback generado
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            [4, 4, 60, 60], radius=14,
            fill=(27, 30, 36, 255),
            outline=(255, 92, 22, 255), width=3,
        )
        draw.ellipse([20, 20, 44, 44], fill=(255, 92, 22, 230))
        return img

    def _history_items(self):
        """Genera el submenú de historial cada vez que se abre el menú."""
        entries = self.app.history.entries()
        if not entries:
            yield pystray.MenuItem(tr("tray.no_history"), None, enabled=False)
            return
        def _make_action(entry):
            return lambda icon, item: self.app.schedule(self.app.open_history_entry, entry)

        for entry in entries:
            yield pystray.MenuItem(
                entry.menu_title(),
                _make_action(entry),
            )
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem(
            tr("tray.clear_history"), lambda icon, item: self.app.history.clear()
        )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(f"{APP_NAME} v{APP_VERSION}", None, enabled=False),
            pystray.MenuItem(
                lambda item: tr(
                    "tray.install_update",
                    version=self.app.pending_update.version if self.app.pending_update else "",
                ),
                lambda icon, item: self.app.schedule(self.app.show_update_dialog),
                visible=lambda item: self.app.pending_update is not None,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(tr("tray.history"), pystray.Menu(self._history_items)),
            pystray.MenuItem(
                tr("tray.config"),
                lambda icon, item: self.app.schedule(self.app.open_config),
                default=True,
            ),
            pystray.MenuItem(
                tr("tray.check_updates"),
                lambda icon, item: self.app.schedule(self.app.check_updates_now),
            ),
            pystray.MenuItem(
                tr("tray.about"),
                lambda icon, item: self.app.schedule(self.app.open_about),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                tr("tray.quit"),
                lambda icon, item: self.app.schedule(self.app.quit_app),
            ),
        )

    def start(self):
        image = self._build_image()
        self.icon = pystray.Icon(
            APP_NAME, image,
            tr("tray.tooltip", app=APP_NAME, hotkey=active_hotkey_label()),
            self._build_menu(),
        )
        if IS_MAC:
            # En macOS el ícono debe vivir en el hilo principal; run_detached lo
            # integra con el bucle de eventos de Cocoa que ya mueve Tk.
            self.icon.run_detached()
        else:
            threading.Thread(target=self.icon.run, daemon=True).start()

    def update_hotkey(self):
        """Actualiza el tooltip del ícono cuando cambia el atajo global."""
        if self.icon:
            try:
                self.icon.title = tr("tray.tooltip", app=APP_NAME, hotkey=active_hotkey_label())
            except Exception:
                pass

    def update_language(self):
        """Reconstruye el menú y el tooltip cuando cambia el idioma."""
        if self.icon:
            try:
                self.icon.menu = self._build_menu()
                self.update_hotkey()
                self.refresh()
            except Exception:
                pass

    def refresh(self):
        """Reconstruye el menú (necesario en Windows para el submenú dinámico)."""
        if self.icon:
            try:
                self.icon.update_menu()
            except Exception:
                pass

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

