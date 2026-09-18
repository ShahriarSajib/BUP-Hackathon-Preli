import json
import logging
import time
from typing import List

import httpx

from app.config import settings
from app.interpreter.base import LLMError, LLMProvider
from app.interpreter.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.base_url = settings.GEMINI_BASE_URL.rstrip("/")

    def interpret(self, notes: List[str], battery_capacity: float) -> dict:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": build_user_prompt(notes)}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }
        params = {"key": self.api_key}
        max_attempts = 1 + max(1, settings.LLM_FALLBACK_MAX_RETRIES)
        with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            for attempt in range(max_attempts):
                resp = client.post(url, params=params, json=payload)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_attempts - 1:
                    delay = _retry_delay(resp)
                    logger.warning(
                        "gemini status %s (attempt %d/%d); backing off %.1fs",
                        resp.status_code, attempt + 1, max_attempts, delay,
                    )
                    time.sleep(delay)
                    continue
                if resp.status_code != 200:
                    logger.warning(
                        "gemini http %s: %s", resp.status_code, resp.text[:500]
                    )
                    raise LLMError(f"gemini status {resp.status_code}")
                break
            data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LLMError("gemini output missing content") from exc
        parsed = json.loads(text)
        if not isinstance(parsed, dict) or "notes" not in parsed:
            raise LLMError("gemini output missing notes array")
        return parsed


def _retry_delay(resp: httpx.Response) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return min(15.0, float(retry_after) + 0.5)
        except ValueError:
            pass
    return 3.0