"""
Escriba — Icono del System Tray.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import pystray
from PIL import Image, ImageDraw

from constants import APP_NAME, APP_VERSION, BASE_DIR
from plataforma import HOTKEY_LABEL, IS_MAC

if TYPE_CHECKING:
    from escriba import EscribaApp


class TrayIconManager:
    """Crea y gestiona el ícono en la bandeja del sistema."""

    def __init__(self, app: EscribaApp):
        self.app = app
        self.icon = None

    @staticmethod
    def _build_image() -> Image.Image:
        ico_path = os.path.join(BASE_DIR, "escriba.ico")
        if os.path.exists(ico_path):
            try:
                img = Image.open(ico_path)
                img = img.convert("RGBA").resize((64, 64), Image.LANCZOS)
                return img
            except Exception:
                pass
        # Fallback generado
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            [4, 4, 60, 60], radius=14,
            fill=(18, 16, 32, 255),
            outline=(0, 210, 180, 255), width=3,
        )
        draw.ellipse([20, 20, 44, 44], fill=(0, 210, 180, 200))
        return img

    def _history_items(self):
        """Genera el submenú de historial cada vez que se abre el menú."""
        entries = self.app.history.entries()
        if not entries:
            yield pystray.MenuItem("(sin respuestas todavía)", None, enabled=False)
            return
        for entry in entries:
            yield pystray.MenuItem(
                entry.menu_title(),
                lambda icon, item, e=entry: self.app.schedule(self.app.open_history_entry, e),
            )
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem(
            "🗑️  Borrar historial", lambda icon, item: self.app.history.clear()
        )

    def start(self):
        image = self._build_image()
        menu = pystray.Menu(
            pystray.MenuItem(f"{APP_NAME} v{APP_VERSION}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🕘  Historial", pystray.Menu(self._history_items)),
            pystray.MenuItem(
                "⚙️  Configuración",
                lambda icon, item: self.app.schedule(self.app.open_config),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "❌  Salir",
                lambda icon, item: self.app.schedule(self.app.quit_app),
            ),
        )
        self.icon = pystray.Icon(
            APP_NAME, image,
            f"{APP_NAME} — {HOTKEY_LABEL} para activar",
            menu,
        )
        if IS_MAC:
            # En macOS el ícono debe vivir en el hilo principal; run_detached lo
            # integra con el bucle de eventos de Cocoa que ya mueve Tk.
            self.icon.run_detached()
        else:
            threading.Thread(target=self.icon.run, daemon=True).start()

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
