"""
Escriba — Persistencia de configuración (config.json).
"""

import os
import json

from constants import CONFIG_FILE
from startup import StartupManager


class ConfigManager:
    """Lee y escribe la configuración de la app en disco."""

    @staticmethod
    def load() -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # Primer arranque: crear config con autostart activado
        default = {"api_key": "", "autostart": True}
        ConfigManager.save(default)
        StartupManager.enable()
        return default

    @staticmethod
    def save(data: dict):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def get(key: str, default=None):
        return ConfigManager.load().get(key, default)

    @staticmethod
    def set(key: str, value):
        data = ConfigManager.load()
        data[key] = value
        ConfigManager.save(data)

    @staticmethod
    def get_api_key() -> str:
        return ConfigManager.get("api_key", "")

    @staticmethod
    def is_configured() -> bool:
        return bool(ConfigManager.get_api_key().strip())
