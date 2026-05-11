"""
Escriba — Persistencia de configuración (config.json).
"""

import os
import json

from constants import CONFIG_FILE
from startup import StartupManager


class ConfigManager:
    """Lee y escribe la configuración de la app en disco."""

    _cache: dict | None = None

    @classmethod
    def load(cls) -> dict:
        if cls._cache is not None:
            return cls._cache
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cls._cache = json.load(f)
                    return cls._cache
            except Exception:
                pass
        # Primer arranque: crear config por defecto
        default_config = {"api_key": "", "autostart": True}
        cls.save(default_config)
        cls._cache = default_config
        return default_config

    @classmethod
    def save(cls, data: dict):
        cls._cache = data
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def get(cls, key: str, default=None):
        return cls.load().get(key, default)

    @classmethod
    def set(cls, key: str, value):
        data = cls.load()
        data[key] = value
        cls.save(data)

    @staticmethod
    def get_api_key() -> str:
        return ConfigManager.get("api_key", "")

    @staticmethod
    def is_configured() -> bool:
        return bool(ConfigManager.get_api_key().strip())
