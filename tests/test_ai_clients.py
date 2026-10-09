from unittest.mock import MagicMock, patch

import pytest
import requests

from constants import GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODELS
from ai_clients import (
    GeminiClient,
    generate_with_fallback,
    is_retryable_error,
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

    def test_generate_retry_on_429_then_succeed(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.time.sleep") as mock_sleep,
            patch("ai_clients.requests.post") as mock_post,
        ):
            resp_429 = requests.Response()
            resp_429.status_code = 429
            resp_429.json = MagicMock(return_value={"error": {"message": "Resource has been exhausted"}})
            err_429 = requests.exceptions.HTTPError(response=resp_429)

            resp_ok = MagicMock()
            resp_ok.raise_for_status.return_value = None
            resp_ok.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "Respuesta tras reintento"}]}}]
            }

            mock_post.side_effect = [err_429, resp_ok]
            retry_callback = MagicMock()

            result = GeminiClient.generate("prompt", "text", max_retries=3, initial_delay=0.1, on_retry=retry_callback)

            assert result == "Respuesta tras reintento"
            assert mock_post.call_count == 2
            mock_sleep.assert_called_once()
            retry_callback.assert_called_once()
            assert retry_callback.call_args[0][0] == 1  # attempt 1
            assert retry_callback.call_args[0][1] == 3  # max retries

    def test_generate_retry_on_503_overloaded_then_succeed(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.time.sleep"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            resp_503 = requests.Response()
            resp_503.status_code = 503
            resp_503.json = MagicMock(return_value={"error": {"message": "The model is overloaded. Please try again later."}})
            err_503 = requests.exceptions.HTTPError(response=resp_503)

            resp_ok = MagicMock()
            resp_ok.raise_for_status.return_value = None
            resp_ok.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "Éxito al tercer intento"}]}}]
            }

            mock_post.side_effect = [err_503, err_503, resp_ok]

            result = GeminiClient.generate("prompt", "text", max_retries=3, initial_delay=0.1)
            assert result == "Éxito al tercer intento"
            assert mock_post.call_count == 3

    def test_generate_retry_exhausted_on_429(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.time.sleep"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            resp_429 = requests.Response()
            resp_429.status_code = 429
            resp_429.json = MagicMock(return_value={"error": {"message": "Resource has been exhausted"}})
            err_429 = requests.exceptions.HTTPError(response=resp_429)
            mock_post.side_effect = err_429

            with pytest.raises(RuntimeError, match="ocupado o con límite de uso excedido.*Reintentos agotados"):
                GeminiClient.generate("prompt", "text", max_retries=2, initial_delay=0.01)

            assert mock_post.call_count == 2

    def test_generate_retry_on_text_overloaded_message(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.time.sleep"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            resp_busy = MagicMock()
            resp_busy.raise_for_status.return_value = None
            resp_busy.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "El modelo está ocupado en este momento por mucho uso"}]}}]
            }

            resp_ok = MagicMock()
            resp_ok.raise_for_status.return_value = None
            resp_ok.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "Texto generado correctamente"}]}}]
            }

            mock_post.side_effect = [resp_busy, resp_ok]

            result = GeminiClient.generate("prompt", "text", max_retries=2, initial_delay=0.01)
            assert result == "Texto generado correctamente"
            assert mock_post.call_count == 2

    def test_generate_connection_error_exhausted(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.time.sleep"),
            patch(
                "ai_clients.requests.post",
                side_effect=requests.exceptions.ConnectionError,
            ) as mock_post,
        ):
            with pytest.raises(RuntimeError, match="Error de red"):
                GeminiClient.generate("prompt", "text", max_retries=2, initial_delay=0.01)
            assert mock_post.call_count == 2

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


class TestIsRetryableError:
    def test_connection_and_timeout(self):
        is_ret, reason = is_retryable_error(requests.exceptions.ConnectionError())
        assert is_ret is True

        is_ret, reason = is_retryable_error(requests.exceptions.Timeout())
        assert is_ret is True

    def test_http_status_codes(self):
        resp_429 = requests.Response()
        resp_429.status_code = 429
        is_ret, reason = is_retryable_error(requests.exceptions.HTTPError(response=resp_429))
        assert is_ret is True

        resp_503 = requests.Response()
        resp_503.status_code = 503
        is_ret, reason = is_retryable_error(requests.exceptions.HTTPError(response=resp_503))
        assert is_ret is True

        resp_400 = requests.Response()
        resp_400.status_code = 400
        is_ret, reason = is_retryable_error(requests.exceptions.HTTPError(response=resp_400))
        assert is_ret is False


class TestGenerateWithFallback:
    def test_uses_gemini_with_callback(self):
        callback = MagicMock()
        with patch("ai_clients.GeminiClient.generate", return_value="gemini result") as mock_gemini:
            result, provider = generate_with_fallback("prompt", "text", on_retry=callback)

            assert result == "gemini result"
            assert provider == "gemini"
            mock_gemini.assert_called_once_with("prompt", "text", on_retry=callback)
