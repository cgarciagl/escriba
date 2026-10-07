from unittest.mock import MagicMock, patch

import pytest
import requests

from constants import GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODELS
from ai_clients import (
    GeminiClient,
    generate_with_fallback,
)


class TestGeminiClient:
    def test_generate_success(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="fake_gemini_key"),
            patch("ai_clients.ConfigManager.get", return_value="gemini-3.5-flash-lite"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "  Texto generado por Gemini  "}]
                        }
                    }
                ]
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            result = GeminiClient.generate("traduce", "hello")

            assert result == "Texto generado por Gemini"
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert "gemini-3.5-flash-lite" in args[0]
            assert kwargs["headers"]["x-goog-api-key"] == "fake_gemini_key"
            assert kwargs["json"]["contents"][0]["parts"][0]["text"] == "traduce\n\n---\n\nhello"

    def test_generate_no_api_key(self):
        with patch("ai_clients.ConfigManager.get_api_key", return_value=""):
            with pytest.raises(ValueError, match="API Key de Google Gemini no configurada"):
                GeminiClient.generate("prompt", "text")

    def test_generate_empty_candidates(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {"candidates": []}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            with pytest.raises(RuntimeError, match="no contiene contenido válido"):
                GeminiClient.generate("prompt", "text")

    def test_generate_empty_text_part(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "candidates": [{"content": {"parts": []}}]
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            with pytest.raises(RuntimeError, match="vino vacía"):
                GeminiClient.generate("prompt", "text")

    def test_generate_http_error_with_json_message(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="bad_key"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            response = requests.Response()
            response.status_code = 400
            response.json = MagicMock(return_value={"error": {"message": "API key not valid"}})
            exc = requests.exceptions.HTTPError(response=response)
            mock_post.side_effect = exc

            with pytest.raises(RuntimeError, match="Gemini HTTP 400: API key not valid"):
                GeminiClient.generate("prompt", "text")

    def test_generate_connection_error(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch(
                "ai_clients.requests.post",
                side_effect=requests.exceptions.ConnectionError,
            ),
        ):
            with pytest.raises(RuntimeError, match="Error de red"):
                GeminiClient.generate("prompt", "text")

    def test_fetch_available_models_success(self):
        with patch("ai_clients.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "models": [
                    {
                        "name": "models/gemini-2.5-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-3.5-flash-lite",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-3.1-flash-tts-preview",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/embedding-001",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ]
            }
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            models = GeminiClient.fetch_available_models("test_key")

            # gemini-3.5-flash-lite must be first, tts excluded, embedding excluded
            assert models[0] == GEMINI_DEFAULT_MODEL
            assert "gemini-2.5-flash" in models
            assert "gemini-3.1-flash-tts-preview" not in models
            assert "embedding-001" not in models

    def test_fetch_available_models_no_key_returns_fallback(self):
        models = GeminiClient.fetch_available_models("")
        assert models == GEMINI_FALLBACK_MODELS

    def test_fetch_available_models_network_failure_returns_fallback(self):
        with patch("ai_clients.requests.get", side_effect=requests.exceptions.ConnectionError):
            models = GeminiClient.fetch_available_models("test_key")
            assert models == GEMINI_FALLBACK_MODELS


class TestGenerateWithFallback:
    def test_uses_gemini(self):
        with patch("ai_clients.GeminiClient.generate", return_value="gemini result") as mock_gemini:
            result, provider = generate_with_fallback("prompt", "text")

            assert result == "gemini result"
            assert provider == "gemini"
            mock_gemini.assert_called_once_with("prompt", "text")
