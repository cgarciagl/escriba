import hashlib
import io
import os
import tarfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import updater
from updater import (
    ReleaseInfo,
    UpdateCancelled,
    apply_update_and_restart,
    check_for_update,
    download_and_prepare,
    is_newer_version,
    parse_version,
    platform_asset_name,
    should_auto_check,
)


class TestVersionComparison:
    def test_parse_version_strips_v_and_suffix(self):
        assert parse_version("v0.0.6") == (0, 0, 6)
        assert parse_version("V1.2.3-beta") == (1, 2, 3)
        assert parse_version("2.0") == (2, 0)

    def test_is_newer_version(self):
        assert is_newer_version("v0.0.7", "0.0.6") is True
        assert is_newer_version("v0.1.0", "0.0.6") is True
        assert is_newer_version("v0.0.6", "0.0.6") is False
        assert is_newer_version("v0.0.5", "0.0.6") is False
        assert is_newer_version("v1.0", "0.9.9") is True


class TestPlatformAssetName:
    def test_assets_by_platform(self):
        assert platform_asset_name("win32") == "Escriba.exe"
        assert platform_asset_name("darwin") == "Escriba-macos.zip"
        assert platform_asset_name("linux") == "Escriba-linux.tar.gz"


class TestShouldAutoCheck:
    def test_disabled_in_config(self):
        with patch.object(updater.ConfigManager, "get", side_effect=lambda k, d=None: False if k == "auto_update_check" else 0):
            assert should_auto_check(now=1000000) is False

    def test_skips_when_checked_recently(self):
        now = 1_000_000
        def fake_get(k, d=None):
            if k == "auto_update_check":
                return True
            if k == "last_update_check":
                return now - 3600  # hace 1 hora
            return d

        with patch.object(updater.ConfigManager, "get", side_effect=fake_get):
            assert should_auto_check(now=now) is False

    def test_runs_when_interval_elapsed(self):
        now = 1_000_000
        def fake_get(k, d=None):
            if k == "auto_update_check":
                return True
            if k == "last_update_check":
                return now - 90000  # > 24 h
            return d

        with patch.object(updater.ConfigManager, "get", side_effect=fake_get):
            assert should_auto_check(now=now) is True


class TestCheckForUpdate:
    def test_returns_release_info_when_newer_version_available(self):
        payload = {
            "tag_name": "v9.9.9",
            "html_url": "https://github.com/cgarciagl/escriba/releases/tag/v9.9.9",
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": platform_asset_name(),
                    "browser_download_url": "https://example.com/asset",
                    "size": 1234,
                    "digest": "sha256:abcdef",
                }
            ],
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status.return_value = None

        with (
            patch("updater.requests.get", return_value=mock_resp),
            patch.object(updater.ConfigManager, "set") as mock_set,
        ):
            info, err = check_for_update()

        assert err is None
        assert info is not None
        assert info.version == "9.9.9"
        assert info.asset_url == "https://example.com/asset"
        assert info.asset_sha256 == "abcdef"
        mock_set.assert_called_once()

    def test_returns_none_when_up_to_date(self):
        payload = {
            "tag_name": f"v{updater.APP_VERSION}",
            "draft": False,
            "prerelease": False,
            "assets": [],
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status.return_value = None

        with (
            patch("updater.requests.get", return_value=mock_resp),
            patch.object(updater.ConfigManager, "set"),
        ):
            info, err = check_for_update()

        assert info is None
        assert err is None

    def test_ignores_draft_and_prerelease(self):
        payload = {"tag_name": "v9.9.9", "draft": False, "prerelease": True, "assets": []}
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status.return_value = None

        with (
            patch("updater.requests.get", return_value=mock_resp),
            patch.object(updater.ConfigManager, "set"),
        ):
            info, err = check_for_update()

        assert info is None
        assert err is None

    def test_returns_error_on_network_failure(self):
        with patch("updater.requests.get", side_effect=OSError("sin red")):
            info, err = check_for_update()

        assert info is None
        assert "sin red" in err


class TestDownloadAndPrepare:
    @staticmethod
    def _build_linux_tar_gz(binary_bytes: bytes) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            ti = tarfile.TarInfo("Escriba")
            ti.size = len(binary_bytes)
            tf.addfile(ti, io.BytesIO(binary_bytes))
        return buf.getvalue()

    def test_downloads_verifies_sha256_and_extracts_linux(self, tmp_path):
        archive = self._build_linux_tar_gz(b"#!/bin/sh\necho ok\n")
        sha = hashlib.sha256(archive).hexdigest()
        info = ReleaseInfo(
            version="9.9.9",
            tag="v9.9.9",
            html_url="https://example.com",
            asset_name="Escriba-linux.tar.gz",
            asset_url="https://example.com/Escriba-linux.tar.gz",
            asset_size=len(archive),
            asset_sha256=sha,
        )

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_resp.headers = {"Content-Length": str(len(archive))}
        mock_resp.iter_content.return_value = [archive[:16], archive[16:]]
        mock_resp.raise_for_status.return_value = None

        progress = []
        with (
            patch("updater.sys.platform", "linux"),
            patch("updater.requests.get", return_value=mock_resp),
            patch("updater.tempfile.mkdtemp", return_value=str(tmp_path)),
        ):
            target = download_and_prepare(info, on_progress=progress.append)

        assert os.path.isfile(target)
        assert os.path.basename(target) == "Escriba"
        assert progress[-1] == 100

    def test_raises_on_sha256_mismatch(self, tmp_path):
        data = b"corrupted payload"
        info = ReleaseInfo(
            version="9.9.9",
            tag="v9.9.9",
            html_url="https://example.com",
            asset_name="Escriba-linux.tar.gz",
            asset_url="https://example.com/Escriba-linux.tar.gz",
            asset_size=len(data),
            asset_sha256="0" * 64,
        )

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_resp.headers = {"Content-Length": str(len(data))}
        mock_resp.iter_content.return_value = [data]
        mock_resp.raise_for_status.return_value = None

        with (
            patch("updater.sys.platform", "linux"),
            patch("updater.requests.get", return_value=mock_resp),
            patch("updater.tempfile.mkdtemp", return_value=str(tmp_path / "stage")),
        ):
            os.makedirs(tmp_path / "stage", exist_ok=True)
            with pytest.raises(RuntimeError, match="SHA-256"):
                download_and_prepare(info)

    def test_cancel_event_aborts_download(self, tmp_path):
        info = ReleaseInfo(
            version="9.9.9",
            tag="v9.9.9",
            html_url="https://example.com",
            asset_name="Escriba-linux.tar.gz",
            asset_url="https://example.com/Escriba-linux.tar.gz",
        )
        cancel = threading.Event()
        cancel.set()

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_resp.headers = {}
        mock_resp.iter_content.return_value = [b"chunk"]
        mock_resp.raise_for_status.return_value = None

        with (
            patch("updater.requests.get", return_value=mock_resp),
            patch("updater.tempfile.mkdtemp", return_value=str(tmp_path / "stage")),
        ):
            os.makedirs(tmp_path / "stage", exist_ok=True)
            with pytest.raises(UpdateCancelled):
                download_and_prepare(info, cancel_event=cancel)


class TestApplyUpdateAndRestart:
    def test_spawns_linux_replacer_and_quits(self, tmp_path):
        new_bin = tmp_path / "extracted" / "Escriba"
        new_bin.parent.mkdir(parents=True)
        new_bin.write_bytes(b"new")
        on_quit = MagicMock()

        with (
            patch("updater.sys.platform", "linux"),
            patch("updater.sys.executable", "/opt/escriba/Escriba"),
            patch("updater.subprocess.Popen") as mock_popen,
        ):
            apply_update_and_restart(str(new_bin), on_quit)

        mock_popen.assert_called_once()
        on_quit.assert_called_once()
