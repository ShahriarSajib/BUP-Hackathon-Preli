import json
import logging
import time
from typing import List

import httpx

from app.config import settings
from app.interpreter.base import LLMError, LLMProvider
from app.interpreter.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

# Groq OpenAI-compatible JSON schema for stricter models (gpt-oss family).
_GROQ_SCHEMA = {
    "name": "operator_notes_interpretation",
    "schema": {
        "type": "object",
        "properties": {
            "notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "note_index": {"type": "integer"},
                        "directive_type": {"type": "string"},
                        "applies": {"type": "boolean"},
                        "start_hour": {"type": ["integer", "null"]},
                        "end_hour": {"type": ["integer", "null"]},
                        "factor": {"type": ["number", "null"]},
                        "minimum_energy_kwh": {"type": ["number", "null"]},
                        "minimum_energy_fraction": {"type": ["number", "null"]},
                        "max_grid_kwh": {"type": ["number", "null"]},
                    },
                    "required": [
                        "note_index",
                        "directive_type",
                        "applies",
                        "start_hour",
                        "end_hour",
                        "factor",
                        "minimum_energy_kwh",
                        "minimum_energy_fraction",
                        "max_grid_kwh",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["notes"],
        "additionalProperties": False,
    },
    "strict": True,
}


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL
        self.base_url = settings.GROQ_BASE_URL.rstrip("/")

    def interpret(self, notes: List[str], battery_capacity: float) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(notes)},
        ]
        url = f"{self.base_url}/chat/completions"
        max_attempts = 1 + max(1, settings.LLM_PRIMARY_MAX_RETRIES)
        with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            for attempt in range(max_attempts):
                strict_payload = {
                    "model": self.model,
                    "temperature": 0,
                    "messages": messages,
                    "response_format": {"type": "json_schema", "json_schema": _GROQ_SCHEMA},
                    "max_tokens": 2048,
                }
                resp = client.post(url, headers=headers, json=strict_payload)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_attempts - 1:
                    delay = _retry_delay(resp)
                    logger.warning(
                        "groq status %s (attempt %d/%d); backing off %.1fs",
                        resp.status_code, attempt + 1, max_attempts, delay,
                    )
                    time.sleep(delay)
                    continue
                if resp.status_code != 200:
                    logger.info(
                        "groq strict json_schema unavailable (%s); retrying with json_object",
                        resp.status_code,
                    )
                    fallback_payload = {
                        "model": self.model,
                        "temperature": 0,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                        "max_tokens": 2048,
                    }
                    resp = client.post(url, headers=headers, json=fallback_payload)
                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_attempts - 1:
                        delay = _retry_delay(resp)
                        logger.warning(
                            "groq json_object status %s; backing off %.1fs",
                            resp.status_code, delay,
                        )
                        time.sleep(delay)
                        continue
                if resp.status_code != 200:
                    logger.warning("groq http %s: %s", resp.status_code, resp.text[:300])
                    raise LLMError(f"groq status {resp.status_code}")
                break
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        logger.info("groq llm response: %s", content)
        parsed = json.loads(content)
        if not isinstance(parsed, dict) or "notes" not in parsed:
            raise LLMError("groq output missing notes array")
        return parsed


def _retry_delay(resp: httpx.Response) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return min(15.0, float(retry_after) + 0.5)
        except ValueError:
            pass
    return 3.0