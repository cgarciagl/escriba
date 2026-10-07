"""
Escriba — Cliente de IA para Google Gemini.
"""

import requests

from constants import (
    GEMINI_BASE,
    GEMINI_DEFAULT_MODEL,
    GEMINI_FALLBACK_MODELS,
)
from config import ConfigManager


# ─────────────────────────────────────────────────────────────
# Cliente Google Gemini — API oficial
# ─────────────────────────────────────────────────────────────
class GeminiClient:
    """Llama a la API oficial de Google Gemini y gestiona la lista de modelos."""

    @classmethod
    def fetch_available_models(cls, api_key: str | None = None) -> list[str]:
        """Descarga la lista de modelos Gemini válidos para generateContent."""
        key = api_key or ConfigManager.get_api_key()
        if not key:
            return list(GEMINI_FALLBACK_MODELS)

        url = GEMINI_BASE
        try:
            response = requests.get(
                url,
                headers={"x-goog-api-key": key},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            raw_models = data.get("models", [])
            valid_models = []

            # Excluir modelos especializados que no son de generación de texto general
            excluded_keywords = [
                "tts", "image", "transcribe", "robotics", "computer-use", "customtools"
            ]

            for m in raw_models:
                methods = m.get("supportedGenerationMethods", [])
                name = m.get("name", "").replace("models/", "").strip()
                if "generateContent" in methods and name.startswith("gemini"):
                    if not any(kw in name.lower() for kw in excluded_keywords):
                        valid_models.append(name)

            if not valid_models:
                return list(GEMINI_FALLBACK_MODELS)

            # Asegurar que gemini-3.5-flash-lite esté al principio
            if GEMINI_DEFAULT_MODEL in valid_models:
                valid_models.remove(GEMINI_DEFAULT_MODEL)
                valid_models.insert(0, GEMINI_DEFAULT_MODEL)
            else:
                valid_models.insert(0, GEMINI_DEFAULT_MODEL)

            return valid_models
        except Exception:
            return list(GEMINI_FALLBACK_MODELS)

    @classmethod
    def generate(cls, prompt: str, text: str) -> str:
        api_key = ConfigManager.get_api_key()
        if not api_key:
            raise ValueError("API Key de Google Gemini no configurada.")

        model = ConfigManager.get("model", GEMINI_DEFAULT_MODEL)
        url = f"{GEMINI_BASE}/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": f"{prompt}\n\n---\n\n{text}"}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096},
        }
        try:
            response = requests.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates or "content" not in candidates[0]:
                raise RuntimeError("La respuesta de Gemini no contiene contenido válido.")
            parts = candidates[0]["content"].get("parts", [])
            if not parts or "text" not in parts[0]:
                raise RuntimeError("La respuesta de Gemini vino vacía.")
            return parts[0]["text"].strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Error de red: No se pudo conectar a Google Gemini. Revisa tu conexión a internet.")
        except requests.exceptions.HTTPError as e:
            error_details = ""
            try:
                err_json = e.response.json()
                if "error" in err_json and "message" in err_json["error"]:
                    error_details = f": {err_json['error']['message']}"
            except Exception:
                error_details = f": {e.response.text[:200]}"
            raise RuntimeError(f"Gemini HTTP {e.response.status_code}{error_details}")
        except Exception as e:
            raise RuntimeError(f"Gemini: {e}")


# ─────────────────────────────────────────────────────────────
# Entrada unificada
# ─────────────────────────────────────────────────────────────
def generate_with_fallback(prompt: str, text: str) -> tuple[str, str]:
    """Genera respuesta utilizando Google Gemini con el modelo configurado.

    Returns:
        (resultado: str, provider: str)  donde provider es "gemini".
    """
    result = GeminiClient.generate(prompt, text)
    return result, "gemini"
