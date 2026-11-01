import json

import pytest

from config import ConfigManager


class TestConfigManagerLoad:
    def test_load_creates_default_when_no_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        data = ConfigManager.load()

        assert data == {"api_key": "", "model": "gemini-3.5-flash-lite", "autostart": False}
        assert config_file.exists()
        assert json.loads(config_file.read_text(encoding="utf-8")) == data

    def test_load_reads_existing_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps({"api_key": "abc123", "model": "gemini-2.5-flash", "autostart": False}), encoding="utf-8"
        )
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        data = ConfigManager.load()

        assert data == {"api_key": "abc123", "model": "gemini-2.5-flash", "autostart": False}

    def test_load_handles_corrupted_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json", encoding="utf-8")
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        data = ConfigManager.load()

        assert data == {"api_key": "", "model": "gemini-3.5-flash-lite", "autostart": False}

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


class TestConfigManagerModel:
    def test_get_model_default(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        assert ConfigManager.get_model() == "gemini-3.5-flash-lite"

    def test_set_and_get_model(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        ConfigManager.set_model("gemini-2.5-pro")
        assert ConfigManager.get_model() == "gemini-2.5-pro"


class TestApiKeyStorage:
    def test_plain_storage_when_dpapi_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.CONFIG_FILE", str(tmp_path / "config.json"))
        monkeypatch.setattr("config._dpapi_available", lambda: False)

        ConfigManager.set_api_key("  secreta  ")

        assert ConfigManager.get_api_key() == "secreta"
        assert "api_key_enc" not in ConfigManager.load()

    def test_encrypted_storage_when_dpapi_available(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))
        monkeypatch.setattr("config._dpapi_available", lambda: True)
        monkeypatch.setattr("config.encrypt_secret", lambda v: "ENC:" + v[::-1])
        monkeypatch.setattr("config.decrypt_secret", lambda v: v[4:][::-1])

        ConfigManager.set_api_key("secreta")

        on_disk = json.loads(config_file.read_text(encoding="utf-8"))
        assert on_disk["api_key"] == ""
        assert on_disk["api_key_enc"] == "ENC:aterces"
        assert ConfigManager.get_api_key() == "secreta"

    def test_plain_key_is_migrated_to_encrypted(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"api_key": "vieja"}), encoding="utf-8")
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))
        monkeypatch.setattr("config._dpapi_available", lambda: True)
        monkeypatch.setattr("config.encrypt_secret", lambda v: "ENC:" + v)
        monkeypatch.setattr("config.decrypt_secret", lambda v: v[4:])

        assert ConfigManager.get_api_key() == "vieja"

        on_disk = json.loads(config_file.read_text(encoding="utf-8"))
        assert on_disk["api_key"] == ""
        assert on_disk["api_key_enc"] == "ENC:vieja"

    def test_undecryptable_key_returns_empty(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"api_key": "", "api_key_enc": "basura"}), encoding="utf-8")
        monkeypatch.setattr("config.CONFIG_FILE", str(config_file))

        def boom(_):
            raise OSError("no")

        monkeypatch.setattr("config.decrypt_secret", boom)
        assert ConfigManager.get_api_key() == ""


class TestLegacyMigration:
    def test_copies_legacy_config(self, tmp_path, monkeypatch):
        legacy = tmp_path / "old" / "config.json"
        legacy.parent.mkdir()
        legacy.write_text(json.dumps({"api_key": "x", "model": "m", "autostart": True}), encoding="utf-8")
        new = tmp_path / "appdata" / "Escriba" / "config.json"
        monkeypatch.setattr("config.CONFIG_FILE", str(new))
        monkeypatch.setattr("config.LEGACY_CONFIG_FILE", str(legacy))

        data = ConfigManager.load()

        assert new.exists()
        assert data["model"] == "m"


class TestKeychainSecrets:
    @pytest.fixture
    def keychain(self, tmp_path, monkeypatch):
        store = {}
        monkeypatch.setattr("config.CONFIG_FILE", str(tmp_path / "config.json"))
        monkeypatch.setattr("config._keychain_available", lambda: True)
        monkeypatch.setattr("config._dpapi_available", lambda: False)
        monkeypatch.setattr("config.keychain_get", lambda n: store.get(n, ""))
        monkeypatch.setattr("config.keychain_set", lambda n, v: store.__setitem__(n, v))
        return store

    def test_secret_goes_to_keychain_not_file(self, keychain, tmp_path):
        ConfigManager.set_api_key("secreta")

        on_disk = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert keychain["api_key"] == "secreta"
        assert on_disk["api_key"] == "" and on_disk["api_key_keychain"] is True
        assert "secreta" not in json.dumps(on_disk)
        assert ConfigManager.get_api_key() == "secreta"

    def test_plain_key_migrates_to_keychain(self, keychain, tmp_path):
        (tmp_path / "config.json").write_text(json.dumps({"api_key": "vieja"}), encoding="utf-8")

        assert ConfigManager.get_api_key() == "vieja"
        assert keychain["api_key"] == "vieja"
        assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["api_key"] == ""

    def test_clearing_removes_marker(self, keychain, tmp_path):
        ConfigManager.set_api_key("x")
        ConfigManager.set_api_key("")
        on_disk = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert "api_key_keychain" not in on_disk
        assert ConfigManager.get_api_key() == ""
