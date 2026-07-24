from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReceiptCandidate:
    source_id: str
    file_name: str
    content: bytes
    confidence: float = 1.0
    metadata: dict[str, Any] | None = None


class ReceiptProvider(ABC):
    @abstractmethod
    def candidates(self, resource: dict[str, Any]) -> list[ReceiptCandidate]:
        raise NotImplementedError
