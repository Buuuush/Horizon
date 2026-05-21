"""Optional translation helpers for generated enrichment fields."""

from __future__ import annotations

import asyncio
import os
from typing import Iterable, Optional


class DeepLTranslator:
    """Translate text to French with DeepL when an auth key is available.

    The dependency and API key are both optional. If DeepL is unavailable,
    this helper becomes a no-op so the pipeline can keep running.
    """

    def __init__(self, auth_key: Optional[str] = None, auth_key_env: str = "DEEPL_AUTH_KEY"):
        self.auth_key = auth_key if auth_key is not None else os.getenv(auth_key_env)
        self.available = False
        self._translator = None

        if not self.auth_key:
            return

        try:
            import deepl  # type: ignore
        except Exception:
            return

        try:
            self._translator = deepl.Translator(self.auth_key)
            self.available = True
        except Exception:
            self._translator = None
            self.available = False

    async def translate_to_french(self, texts: Iterable[str]) -> list[str]:
        """Translate a list of strings to French, preserving order."""
        text_list = [str(text) for text in texts]
        if not text_list or not self.available or self._translator is None:
            return text_list

        return await asyncio.to_thread(self._translate_sync, text_list)

    def _translate_sync(self, texts: list[str]) -> list[str]:
        if self._translator is None:
            return texts

        payload: list[str] = []
        positions: list[int] = []
        translated = list(texts)

        for index, text in enumerate(texts):
            if str(text).strip():
                payload.append(str(text))
                positions.append(index)

        if not payload:
            return translated

        response = self._translator.translate_text(payload, target_lang="FR")
        responses = response if isinstance(response, list) else [response]

        for index, result in zip(positions, responses):
            translated[index] = getattr(result, "text", str(result))

        return translated