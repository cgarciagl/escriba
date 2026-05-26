import json

import pytest

from config import ConfigManager


class TestConfigManagerLoad:
    def test_load_creates_default_when_no_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        data = ConfigManager.load()

        assert data == {"api_key": "", "autostart": True}
        assert config_file.exists()
        assert json.loads(config_file.read_text(encoding="utf-8")) == data

    def test_load_reads_existing_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"api_key": "abc123", "autostart": False}), encoding="utf-8"
        )
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        data = ConfigManager.load()

        assert data == {"api_key": "abc123", "autostart": False}

    def test_load_handles_corrupted_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json", encoding="utf-8")
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        data = ConfigManager.load()

        assert data == {"api_key": "", "autostart": True}

    def test_cache_avoids_reload(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        ConfigManager.load()
        config_file.write_text(
            json.dumps({"api_key": "changed", "autostart": False}), encoding="utf-8"
        )

        data = ConfigManager.load()
        assert data["api_key"] == ""

    def test_cache_reset_reloads(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        ConfigManager.load()
        config_file.write_text(
            json.dumps({"api_key": "changed", "autostart": False}), encoding="utf-8"
        )
        ConfigManager._cache = None

        data = ConfigManager.load()
        assert data["api_key"] == "changed"


class TestConfigManagerSave:
    def test_save_persists_to_disk(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        ConfigManager.save({"api_key": "saved", "autostart": True})

        assert json.loads(config_file.read_text(encoding="utf-8")) == {
            "api_key": "saved",
            "autostart": True,
        }

    def test_save_updates_cache(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        ConfigManager.save({"api_key": "cached", "autostart": False})
        assert ConfigManager._cache["api_key"] == "cached"


class TestConfigManagerGetSet:
    def test_get_returns_value(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"api_key": "mykey", "autostart": False}), encoding="utf-8"
        )
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        assert ConfigManager.get("api_key") == "mykey"

    def test_get_returns_default_for_missing_key(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        result = ConfigManager.get("nonexistent", "default_val")
        assert result == "default_val"

    def test_set_updates_and_persists(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        ConfigManager.set("api_key", "new_key")

        data = ConfigManager.load()
        assert data["api_key"] == "new_key"
        assert (
            json.loads(config_file.read_text(encoding="utf-8"))["api_key"] == "new_key"
        )

    def test_set_adds_new_key(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        ConfigManager.set("custom_key", "custom_value")

        assert ConfigManager.get("custom_key") == "custom_value"

    def test_save_with_unicode(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        ConfigManager.save({"api_key": "ñóü", "autostart": True})

        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["api_key"] == "ñóü"


class TestConfigManagerApiKey:
    def test_get_api_key_returns_empty_by_default(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        assert ConfigManager.get_api_key() == ""

    def test_get_api_key_after_set(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        ConfigManager.set("api_key", "my-key-123")
        assert ConfigManager.get_api_key() == "my-key-123"

    def test_is_configured_false_when_no_key(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        assert ConfigManager.is_configured() is False

    def test_is_configured_false_when_blank_key(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"api_key": "   ", "autostart": True}), encoding="utf-8"
        )
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        assert ConfigManager.is_configured() is False

    def test_is_configured_true_with_key(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"api_key": "abc", "autostart": True}), encoding="utf-8"
        )
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        assert ConfigManager.is_configured() is True
