import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from constants import GEMINI_DEFAULT_MODEL, GEMINI_FALLBACK_MODELS
from ai_clients import (
    GeminiClient,
    OpenAICompatibleClient,
    generate_text,
    is_retryable_error,
    provider_order,
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
            # Las instrucciones viajan como system instruction, separadas del texto
            assert kwargs["json"]["systemInstruction"]["parts"][0]["text"] == "traduce"
            assert kwargs["json"]["contents"][0]["parts"][0]["text"] == "hello"

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


class TestGenerateText:
    def test_uses_gemini_with_callback(self):
        callback = MagicMock()
        with patch("ai_clients.GeminiClient.generate", return_value="gemini result") as mock_gemini:
            result, provider = generate_text("prompt", "text", on_retry=callback)

            assert result == "gemini result"
            assert provider == "gemini"
            mock_gemini.assert_called_once_with("prompt", "text", on_retry=callback, on_chunk=None)


class TestErrorMessages:
    def test_own_runtime_errors_are_not_double_wrapped(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            mock_response = MagicMock()
            mock_response.json.return_value = {"candidates": []}
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            with pytest.raises(RuntimeError) as exc_info:
                GeminiClient.generate("prompt", "text")
            assert not str(exc_info.value).startswith("Gemini:")


# ─────────────────────────────────────────────────────────────
# Streaming, proveedor alternativo y fallback
# ─────────────────────────────────────────────────────────────
def _sse_response(lines):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.iter_lines.return_value = iter(lines)
    return resp


def _gemini_chunk(text):
    return "data: " + json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]})


def _openai_chunk(text):
    return "data: " + json.dumps({"choices": [{"delta": {"content": text}}]})


class TestGeminiStreaming:
    def test_streams_chunks_and_returns_full_text(self):
        chunks = []
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.ConfigManager.get", return_value="gemini-x"),
            patch("ai_clients.requests.post",
                  return_value=_sse_response(["", _gemini_chunk("Hola "), _gemini_chunk("mundo ")])) as mock_post,
        ):
            result = GeminiClient.generate("p", "t", on_chunk=chunks.append)

        assert result == "Hola mundo"
        assert chunks == ["Hola ", "mundo "]
        url = mock_post.call_args[0][0]
        assert url.endswith("gemini-x:streamGenerateContent?alt=sse")
        assert mock_post.call_args[1]["stream"] is True

    def test_no_retry_after_chunks_were_emitted(self):
        def broken_stream():
            yield _gemini_chunk("parcial")
            raise requests.exceptions.ConnectionError()

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.iter_lines.return_value = broken_stream()
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.time.sleep"),
            patch("ai_clients.requests.post", return_value=resp) as mock_post,
        ):
            with pytest.raises(RuntimeError, match="Error de red"):
                GeminiClient.generate("p", "t", on_chunk=lambda _: None)
        assert mock_post.call_count == 1

    def test_retries_before_first_chunk(self):
        resp_err = MagicMock()
        http_resp = requests.Response()
        http_resp.status_code = 503
        resp_err.raise_for_status.side_effect = requests.exceptions.HTTPError(response=http_resp)
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.time.sleep"),
            patch("ai_clients.requests.post",
                  side_effect=[resp_err, _sse_response([_gemini_chunk("ok")])]) as mock_post,
        ):
            assert GeminiClient.generate("p", "t", on_chunk=lambda _: None) == "ok"
        assert mock_post.call_count == 2

    def test_empty_stream_raises(self):
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.requests.post", return_value=_sse_response([])),
        ):
            with pytest.raises(RuntimeError, match="vino vacía"):
                GeminiClient.generate("p", "t", on_chunk=lambda _: None, max_retries=1)


def _openai_settings(base="http://localhost:11434/v1", model="llama", key=""):
    return patch("ai_clients.OpenAICompatibleClient.settings", return_value=(base, model, key))


class TestOpenAICompatibleClient:
    def test_non_stream_request(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"choices": [{"message": {"content": "  respuesta  "}}]}
        with _openai_settings(key="sk-1"), patch("ai_clients.requests.post", return_value=resp) as mock_post:
            assert OpenAICompatibleClient.generate("instr", "texto") == "respuesta"

        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:11434/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer sk-1"
        assert kwargs["json"]["messages"] == [
            {"role": "system", "content": "instr"},
            {"role": "user", "content": "texto"},
        ]
        assert kwargs["json"]["stream"] is False

    def test_no_auth_header_without_key(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"choices": [{"message": {"content": "x"}}]}
        with _openai_settings(), patch("ai_clients.requests.post", return_value=resp) as mock_post:
            OpenAICompatibleClient.generate("p", "t")
        assert "Authorization" not in mock_post.call_args[1]["headers"]

    def test_streaming(self):
        chunks = []
        lines = [_openai_chunk("Ho"), _openai_chunk("la"), "data: [DONE]", _openai_chunk("ignorado")]
        with _openai_settings(), patch("ai_clients.requests.post", return_value=_sse_response(lines)) as mock_post:
            assert OpenAICompatibleClient.generate("p", "t", on_chunk=chunks.append) == "Hola"
        assert chunks == ["Ho", "la"]
        assert mock_post.call_args[1]["json"]["stream"] is True

    def test_not_configured_raises_value_error(self):
        with _openai_settings(base="", model=""):
            with pytest.raises(ValueError, match="no configurado"):
                OpenAICompatibleClient.generate("p", "t")

    def test_connection_error_message_mentions_provider(self):
        with (
            _openai_settings(),
            patch("ai_clients.time.sleep"),
            patch("ai_clients.requests.post", side_effect=requests.exceptions.ConnectionError),
        ):
            with pytest.raises(RuntimeError, match="proveedor alternativo"):
                OpenAICompatibleClient.generate("p", "t", max_retries=2)

    def test_fetch_models(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"data": [{"id": "b"}, {"id": "a"}]}
        with patch("ai_clients.requests.get", return_value=resp):
            assert OpenAICompatibleClient.fetch_available_models("http://x/v1/") == ["a", "b"]

    def test_fetch_models_failure_returns_empty(self):
        with patch("ai_clients.requests.get", side_effect=requests.exceptions.ConnectionError):
            assert OpenAICompatibleClient.fetch_available_models("http://x/v1") == []


def _config(values):
    return patch("ai_clients.ConfigManager.get", side_effect=lambda k, d=None: values.get(k, d))


class TestProviderSelection:
    def test_default_order_is_gemini_only(self):
        with _config({}):
            assert provider_order() == ["gemini"]

    def test_fallback_added_only_when_configured(self):
        with _config({"provider": "gemini", "fallback_enabled": True}):
            with patch("ai_clients.OpenAICompatibleClient.is_configured", return_value=True):
                assert provider_order() == ["gemini", "openai"]
            with patch("ai_clients.OpenAICompatibleClient.is_configured", return_value=False):
                assert provider_order() == ["gemini"]

    def test_unknown_provider_defaults_to_gemini(self):
        with _config({"provider": "otro"}):
            assert provider_order() == ["gemini"]

    def test_fallback_on_failure(self):
        status = MagicMock()
        with (
            patch("ai_clients.provider_order", return_value=["gemini", "openai"]),
            patch("ai_clients.GeminiClient.generate", side_effect=RuntimeError("caído")),
            patch("ai_clients.OpenAICompatibleClient.generate", return_value="respaldo"),
        ):
            assert generate_text("p", "t", on_status=status) == ("respaldo", "openai")
        status.assert_called_once()

    def test_no_fallback_after_partial_stream(self):
        def partial(prompt, text, on_retry=None, on_chunk=None):
            on_chunk("medio texto")
            raise RuntimeError("cortado")

        with (
            patch("ai_clients.provider_order", return_value=["gemini", "openai"]),
            patch("ai_clients.GeminiClient.generate", side_effect=partial),
            patch("ai_clients.OpenAICompatibleClient.generate") as mock_openai,
        ):
            with pytest.raises(RuntimeError, match="cortado"):
                generate_text("p", "t", on_chunk=lambda _: None)
        mock_openai.assert_not_called()

    def test_last_error_is_raised(self):
        with (
            patch("ai_clients.provider_order", return_value=["gemini", "openai"]),
            patch("ai_clients.GeminiClient.generate", side_effect=RuntimeError("uno")),
            patch("ai_clients.OpenAICompatibleClient.generate", side_effect=RuntimeError("dos")),
        ):
            with pytest.raises(RuntimeError, match="dos"):
                generate_text("p", "t")


# ─────────────────────────────────────────────────────────────
# Cancelación y disponibilidad
# ─────────────────────────────────────────────────────────────
import threading

from ai_clients import CancelledByUser, is_ready


class TestCancellation:
    def test_cancel_before_request(self):
        ev = threading.Event()
        ev.set()
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.requests.post") as mock_post,
        ):
            with pytest.raises(CancelledByUser):
                GeminiClient.generate("p", "t", cancel_event=ev)
        mock_post.assert_not_called()

    def test_cancel_during_stream_stops_and_does_not_retry(self):
        ev = threading.Event()
        chunks = []

        def on_chunk(piece):
            chunks.append(piece)
            ev.set()  # el usuario pulsa Detener tras el primer fragmento

        lines = [_gemini_chunk("uno"), _gemini_chunk("dos"), _gemini_chunk("tres")]
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.requests.post", return_value=_sse_response(lines)) as mock_post,
        ):
            with pytest.raises(CancelledByUser):
                GeminiClient.generate("p", "t", on_chunk=on_chunk, cancel_event=ev)
        assert chunks == ["uno"]
        assert mock_post.call_count == 1

    def test_cancel_during_backoff_wait(self):
        ev = threading.Event()
        http_resp = requests.Response()
        http_resp.status_code = 503
        err = MagicMock()
        err.raise_for_status.side_effect = requests.exceptions.HTTPError(response=http_resp)

        def on_retry(*_):
            ev.set()

        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.requests.post", return_value=err) as mock_post,
        ):
            with pytest.raises(CancelledByUser):
                GeminiClient.generate("p", "t", on_retry=on_retry, cancel_event=ev, initial_delay=5)
        assert mock_post.call_count == 1

    def test_result_discarded_if_cancelled_while_waiting(self):
        ev = threading.Event()
        resp = MagicMock()
        resp.raise_for_status.return_value = None

        def fake_json():
            ev.set()  # se canceló mientras llegaba la respuesta
            return {"candidates": [{"content": {"parts": [{"text": "x"}]}}]}

        resp.json.side_effect = fake_json
        with (
            patch("ai_clients.ConfigManager.get_api_key", return_value="key"),
            patch("ai_clients.requests.post", return_value=resp),
        ):
            with pytest.raises(CancelledByUser):
                GeminiClient.generate("p", "t", cancel_event=ev)

    def test_no_fallback_after_cancel(self):
        with (
            patch("ai_clients.provider_order", return_value=["gemini", "openai"]),
            patch("ai_clients.GeminiClient.generate", side_effect=CancelledByUser()),
            patch("ai_clients.OpenAICompatibleClient.generate") as mock_openai,
        ):
            with pytest.raises(CancelledByUser):
                generate_text("p", "t", cancel_event=threading.Event())
        mock_openai.assert_not_called()


class TestIsReady:
    def test_ready_when_primary_configured(self):
        with patch("ai_clients.provider_order", return_value=["gemini"]), \
             patch("ai_clients.GeminiClient.is_configured", return_value=True):
            assert is_ready()

    def test_not_ready_without_any_provider(self):
        with patch("ai_clients.provider_order", return_value=["gemini"]), \
             patch("ai_clients.GeminiClient.is_configured", return_value=False):
            assert not is_ready()


from ai_clients import needs_configuration


class TestNeedsConfiguration:
    @pytest.mark.parametrize("exc", [
        ValueError("API Key de Google Gemini no configurada."),
        RuntimeError("Gemini HTTP 400: API key not valid. Please pass a valid API key."),
        RuntimeError("Proveedor alternativo HTTP 404: model 'x' not found"),
        RuntimeError("Gemini HTTP 403: Permission denied"),
    ])
    def test_config_errors(self, exc):
        assert needs_configuration(exc)

    @pytest.mark.parametrize("exc", [
        RuntimeError("Error de red: No se pudo conectar a Google Gemini."),
        RuntimeError("El modelo de Gemini está ocupado (HTTP 503)."),
    ])
    def test_transient_errors(self, exc):
        assert not needs_configuration(exc)


def test_iter_sse_data_preserves_utf8_accents():
    import io
    from ai_clients import iter_sse_data

    r = requests.Response()
    r.headers["content-type"] = "text/event-stream"
    r.status_code = 200
    r.encoding = requests.utils.get_encoding_from_headers(r.headers)
    assert r.encoding == "ISO-8859-1"

    payload = json.dumps({"text": "Número promedio en el Índice"}, ensure_ascii=False)
    raw = f"data: {payload}\n\n".encode("utf-8")
    r.raw = io.BytesIO(raw)

    lines = list(iter_sse_data(r))
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["text"] == "Número promedio en el Índice"
