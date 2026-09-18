import logging
from typing import Callable, List, Optional

from app.config import settings
from app.interpreter.deterministic_fallback import interpret_with_rules
from app.interpreter.base import LLMError, LLMProvider
from app.interpreter.groq_provider import GroqProvider
from app.interpreter.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {
    "note_index",
    "directive_type",
    "applies",
    "start_hour",
    "end_hour",
    "factor",
    "minimum_energy_kwh",
    "minimum_energy_fraction",
    "max_grid_kwh",
}


class InterpreterRouter:
    def __init__(
        self,
        primary: Optional[LLMProvider] = None,
        fallback: Optional[LLMProvider] = None,
        rules_interpret: Callable[[List[str]], List[dict]] = interpret_with_rules,
        llm_enabled: Optional[bool] = None,
    ):
        self.rules_interpret = rules_interpret
        self.llm_enabled = (
            settings.llm_enabled if llm_enabled is None else llm_enabled
        )
        self.primary = primary
        self.fallback = fallback
        if self.llm_enabled:
            if self.primary is None and settings.llm_enabled:
                self.primary = GeminiProvider()
            if self.fallback is None and settings.groq_enabled:
                self.fallback = GroqProvider()

    def interpret(self, notes: List[str], battery_capacity: float) -> List[dict]:
        if self.llm_enabled:
            providers = [p for p in (self.primary, self.fallback) if p is not None]
            for provider in providers:
                try:
                    raw = provider.interpret(notes, battery_capacity)
                except LLMError:
                    logger.warning("provider %s failed", provider.name)
                    continue
                except Exception as exc:  # network/parse issues
                    logger.warning("provider %s error: %r", provider.name, exc)
                    continue
                cleaned = self._clean(raw, len(notes))
                if cleaned is not None:
                    return cleaned
                logger.warning("provider %s returned malformed semantics", provider.name)
        return self.rules_interpret(notes)

    @staticmethod
    def _clean(raw, note_count: int) -> Optional[List[dict]]:
        try:
            entries = raw["notes"]
        except (TypeError, KeyError):
            return None
        if not isinstance(entries, list) or len(entries) != note_count:
            return None
        seen = set()
        ordered: List[dict] = [None] * note_count
        for e in entries:
            if not isinstance(e, dict):
                return None
            if not _REQUIRED_KEYS.issubset(e.keys()):
                return None
            idx = e.get("note_index")
            if not isinstance(idx, int) or not (0 <= idx < note_count):
                return None
            if idx in seen:
                return None
            seen.add(idx)
            ordered[idx] = e
        if any(x is None for x in ordered):
            return None
        return ordered