from abc import ABC, abstractmethod
from typing import List


class LLMError(Exception):
    """Raised when a provider cannot produce a parseable structured result."""


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def interpret(self, notes: List[str], battery_capacity: float) -> dict:
        """Return parsed JSON: {"notes": [ {semantic dict per note}, ... ]}"""
        raise NotImplementedError