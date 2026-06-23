"""
Escriba — Clientes de IA (OpenRouter + Pollinations) y lógica de fallback.
"""

import requests

from constants import (
    OPENROUTER_BASE,
    OPENROUTER_DEFAULT_MODEL,
    OPENCODE_BASE,
    OPENCODE_MODEL,
)
from config import ConfigManager


# ─────────────────────────────────────────────────────────────
# Cliente OpenRouter — API compatible con OpenAI
# ─────────────────────────────────────────────────────────────
class OpenRouterClient:
    """Llama a la API de OpenRouter con el modelo configurado."""

    @classmethod
    def generate(cls, prompt: str, text: str) -> str:
        api_key = ConfigManager.get_api_key()
        if not api_key:
            raise ValueError("API Key no configurada.")

        model = ConfigManager.get("model", OPENROUTER_DEFAULT_MODEL)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": f"{prompt}\n\n---\n\n{text}"}],
        }
        try:
            response = requests.post(
                f"{OPENROUTER_BASE}/chat/completions",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "X-Title": "Escriba",
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Error de red: No se pudo conectar a OpenRouter. Revisa tu conexión.")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"OpenRouter HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            raise RuntimeError(f"OpenRouter: {e}")


# ─────────────────────────────────────────────────────────────
# Cliente OpenCode Zen — API compatible con OpenAI, modelo fijo Big Pickle
# ─────────────────────────────────────────────────────────────
class OpenCodeZenClient:
    """Llama a OpenCode Zen usando siempre el modelo Big Pickle."""

    @classmethod
    def generate(cls, prompt: str, text: str) -> str:
        api_key = ConfigManager.get_opencode_api_key()
        if not api_key:
            raise ValueError("API Key de OpenCode Zen no configurada.")

        payload = {
            "model": OPENCODE_MODEL,
            "messages": [{"role": "user", "content": f"{prompt}\n\n---\n\n{text}"}],
        }
        try:
            response = requests.post(
                f"{OPENCODE_BASE}/chat/completions",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "X-Title": "Escriba",
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Error de red: No se pudo conectar a OpenCode Zen. Revisa tu conexión.")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"OpenCode Zen HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            raise RuntimeError(f"OpenCode Zen: {e}")


# ─────────────────────────────────────────────────────────────
# Cliente gratuito — Pollinations AI (sin API Key)
# ─────────────────────────────────────────────────────────────
class FreeAIClient:
    """Fallback gratuito usando Pollinations AI."""

    _ENDPOINT = "https://text.pollinations.ai/"

    @staticmethod
    def generate(prompt: str, text: str) -> str:
        full_prompt = f"{prompt}\n\n---\n\n{text}"
        payload = {
            "messages": [{"role": "user", "content": full_prompt}],
            "model": "openai",
            "private": True,
        }
        try:
            r = requests.post(
                FreeAIClient._ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            r.raise_for_status()
            result = r.text.strip()
            if not result:
                raise RuntimeError("La respuesta fue vacía.")
            return result
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Error de red: No se pudo conectar a Pollinations AI. Revisa tu conexión a Internet.")
        except Exception as e:
            raise RuntimeError(f"Pollinations AI: {e}")


# ─────────────────────────────────────────────────────────────
# Fallback unificado
# ─────────────────────────────────────────────────────────────
def generate_with_fallback(prompt: str, text: str) -> tuple:
    """Cadena de fallback: OpenCode Zen → OpenRouter → Pollinations.

    Intenta cada proveedor configurado en orden y, si falla o no hay key,
    pasa al siguiente. Pollinations (gratuito) es el último recurso.

    Returns:
        (resultado: str, provider: str)  donde provider es uno de
        "opencode", "openrouter" o "pollinations".
    """
    result = None
    provider = ""
    errors = []

    if ConfigManager.is_opencode_configured():
        try:
            result = OpenCodeZenClient.generate(prompt, text)
            provider = "opencode"
        except Exception as e:
            errors.append(f"OpenCode Zen: {e}")

    if result is None and ConfigManager.is_configured():
        try:
            result = OpenRouterClient.generate(prompt, text)
            provider = "openrouter"
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    if result is None:
        try:
            result = FreeAIClient.generate(prompt, text)
            provider = "pollinations"
        except Exception as e:
            errors.append(f"Pollinations: {e}")
            raise RuntimeError(" | ".join(errors))

    return result, provider
