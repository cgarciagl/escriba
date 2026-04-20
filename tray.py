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

if TYPE_CHECKING:
    from escriba import EscribaApp


class TrayIconManager:
    """Crea y gestiona el ícono en la bandeja del sistema."""

    def __init__(self, app: EscribaApp):
        self.app  = app
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
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            [4, 4, 60, 60], radius=14,
            fill=(18, 16, 32, 255),
            outline=(0, 210, 180, 255), width=3,
        )
        draw.ellipse([20, 20, 44, 44], fill=(0, 210, 180, 200))
        return img

    def start(self):
        image = self._build_image()
        menu  = pystray.Menu(
            pystray.MenuItem(f"{APP_NAME} v{APP_VERSION}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "⚙️  Configuración",
                lambda icon, item: self.app.root.after(0, self.app.open_config),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "❌  Salir",
                lambda icon, item: self.app.root.after(0, self.app.quit_app),
            ),
        )
        self.icon = pystray.Icon(
            APP_NAME, image,
            f"{APP_NAME} — Win+Alt+E para activar",
            menu,
        )
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
