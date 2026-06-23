from unittest.mock import patch

import pytest
import requests

from ai_clients import (
    OpenRouterClient,
    OpenCodeZenClient,
    FreeAIClient,
    generate_with_fallback,
)


class TestFreeAIClient:
    def test_generate_success(self):
        with patch("ai_clients.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.text = "Respuesta de prueba"

            result = FreeAIClient.generate("test prompt", "test text")

            assert result == "Respuesta de prueba"
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert kwargs["json"]["messages"][0]["role"] == "user"
            assert "test prompt" in kwargs["json"]["messages"][0]["content"]
            assert "test text" in kwargs["json"]["messages"][0]["content"]
            assert kwargs["json"]["model"] == "openai"
            assert kwargs["json"]["private"] is True

    def test_generate_empty_response(self):
        with patch("ai_clients.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.text = "   "

            with pytest.raises(RuntimeError, match="vacía"):
                FreeAIClient.generate("prompt", "text")

    def test_generate_connection_error(self):
        with patch(
            "ai_clients.requests.post",
            side_effect=requests.exceptions.ConnectionError,
        ):
            with pytest.raises(RuntimeError, match="Error de red"):
                FreeAIClient.generate("prompt", "text")

    def test_generate_http_error(self):
        with patch("ai_clients.requests.post") as mock_post:
            response = requests.Response()
            response.status_code = 500
            exc = requests.exceptions.HTTPError(response=response)
            mock_post.side_effect = exc

            with pytest.raises(RuntimeError, match="Pollinations"):
                FreeAIClient.generate("prompt", "text")


class TestOpenRouterClient:
    def test_generate_success(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="fake_key"),
            patch("ai_clients.ConfigManager.get", return_value="openrouter/free"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "  Resultado limpio  "}}]
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            result = OpenRouterClient.generate("prompt", "text")

            assert result == "Resultado limpio"
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert kwargs["json"]["model"] == "openrouter/free"
            assert "Authorization" in kwargs["headers"]
            assert kwargs["headers"]["Authorization"] == "Bearer fake_key"

    def test_generate_no_api_key(self):
        with patch("ai_clients.ConfigManager.get_api_key", return_value=""):
            with pytest.raises(ValueError, match="no configurada"):
                OpenRouterClient.generate("prompt", "text")

    def test_generate_http_401(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="bad_key"),
            patch("ai_clients.ConfigManager.get", return_value="openrouter/free"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            response = requests.Response()
            response.status_code = 401
            response._content = b'{"error": "unauthorized"}'
            exc = requests.exceptions.HTTPError(response=response)
            mock_post.side_effect = exc

            with pytest.raises(RuntimeError, match="OpenRouter HTTP 401"):
                OpenRouterClient.generate("prompt", "text")

    def test_generate_connection_error(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.ConfigManager.get", return_value="openrouter/free"),
            patch(
                "ai_clients.requests.post",
                side_effect=requests.exceptions.ConnectionError,
            ),
        ):
            with pytest.raises(RuntimeError, match="Error de red"):
                OpenRouterClient.generate("prompt", "text")


class TestOpenCodeZenClient:
    def test_generate_uses_big_pickle_model(self):
        with (
            patch(
                "ai_clients.ConfigManager.get_opencode_api_key",
                return_value="oc_key",
            ),
            patch("ai_clients.requests.post") as mock_post,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "  pepinillo  "}}]
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            result = OpenCodeZenClient.generate("prompt", "text")

            assert result == "pepinillo"
            args, kwargs = mock_post.call_args
            assert kwargs["json"]["model"] == "big-pickle"
            assert kwargs["headers"]["Authorization"] == "Bearer oc_key"
            assert "opencode.ai/zen" in args[0]

    def test_generate_no_api_key(self):
        with patch(
            "ai_clients.ConfigManager.get_opencode_api_key", return_value=""
        ):
            with pytest.raises(ValueError, match="no configurada"):
                OpenCodeZenClient.generate("prompt", "text")


class TestGenerateWithFallback:
    def test_uses_opencode_first_when_configured(self):
        with (
            patch("ai_clients.ConfigManager.is_opencode_configured", return_value=True),
            patch(
                "ai_clients.OpenCodeZenClient.generate", return_value="oc result"
            ) as mock_oc,
            patch("ai_clients.OpenRouterClient.generate") as mock_or,
            patch("ai_clients.FreeAIClient.generate") as mock_free,
        ):
            result, provider = generate_with_fallback("prompt", "text")

            assert result == "oc result"
            assert provider == "opencode"
            mock_oc.assert_called_once_with("prompt", "text")
            mock_or.assert_not_called()
            mock_free.assert_not_called()

    def test_uses_openrouter_when_configured(self):
        with (
            patch("ai_clients.ConfigManager.is_opencode_configured", return_value=False),
            patch("ai_clients.ConfigManager.is_configured", return_value=True),
            patch(
                "ai_clients.OpenRouterClient.generate", return_value="or result"
            ) as mock_or,
            patch("ai_clients.FreeAIClient.generate") as mock_free,
        ):
            result, provider = generate_with_fallback("prompt", "text")

            assert result == "or result"
            assert provider == "openrouter"
            mock_or.assert_called_once_with("prompt", "text")
            mock_free.assert_not_called()

    def test_uses_free_when_not_configured(self):
        with (
            patch("ai_clients.ConfigManager.is_opencode_configured", return_value=False),
            patch("ai_clients.ConfigManager.is_configured", return_value=False),
            patch("ai_clients.OpenRouterClient.generate") as mock_or,
            patch(
                "ai_clients.FreeAIClient.generate", return_value="free result"
            ) as mock_free,
        ):
            result, provider = generate_with_fallback("prompt", "text")

            assert result == "free result"
            assert provider == "pollinations"
            mock_or.assert_not_called()
            mock_free.assert_called_once_with("prompt", "text")

    def test_fallback_from_opencode_to_openrouter(self):
        with (
            patch("ai_clients.ConfigManager.is_opencode_configured", return_value=True),
            patch("ai_clients.ConfigManager.is_configured", return_value=True),
            patch(
                "ai_clients.OpenCodeZenClient.generate",
                side_effect=RuntimeError("OC error"),
            ),
            patch(
                "ai_clients.OpenRouterClient.generate", return_value="or result"
            ) as mock_or,
            patch("ai_clients.FreeAIClient.generate") as mock_free,
        ):
            result, provider = generate_with_fallback("prompt", "text")

            assert result == "or result"
            assert provider == "openrouter"
            mock_or.assert_called_once_with("prompt", "text")
            mock_free.assert_not_called()

    def test_fallback_on_openrouter_failure(self):
        with (
            patch("ai_clients.ConfigManager.is_opencode_configured", return_value=False),
            patch("ai_clients.ConfigManager.is_configured", return_value=True),
            patch(
                "ai_clients.OpenRouterClient.generate",
                side_effect=RuntimeError("OR error"),
            ),
            patch(
                "ai_clients.FreeAIClient.generate", return_value="fallback result"
            ) as mock_free,
        ):
            result, provider = generate_with_fallback("prompt", "text")

            assert result == "fallback result"
            assert provider == "pollinations"
            mock_free.assert_called_once_with("prompt", "text")

    def test_raises_when_all_fail(self):
        with (
            patch("ai_clients.ConfigManager.is_opencode_configured", return_value=True),
            patch("ai_clients.ConfigManager.is_configured", return_value=True),
            patch(
                "ai_clients.OpenCodeZenClient.generate",
                side_effect=RuntimeError("OC error"),
            ),
            patch(
                "ai_clients.OpenRouterClient.generate",
                side_effect=RuntimeError("OR error"),
            ),
            patch(
                "ai_clients.FreeAIClient.generate",
                side_effect=RuntimeError("Free error"),
            ),
        ):
            with pytest.raises(RuntimeError) as excinfo:
                generate_with_fallback("prompt", "text")

            assert "OC error" in str(excinfo.value)
            assert "OR error" in str(excinfo.value)
            assert "Free error" in str(excinfo.value)

    def test_raises_on_free_when_not_configured(self):
        with (
            patch("ai_clients.ConfigManager.is_opencode_configured", return_value=False),
            patch("ai_clients.ConfigManager.is_configured", return_value=False),
            patch(
                "ai_clients.FreeAIClient.generate",
                side_effect=RuntimeError("Free error"),
            ),
        ):
            with pytest.raises(RuntimeError, match="Free error"):
                generate_with_fallback("prompt", "text")


from unittest.mock import MagicMock
