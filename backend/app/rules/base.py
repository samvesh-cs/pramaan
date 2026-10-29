from abc import ABC, abstractmethod
from typing import Any
from app.schemas.finding import FindingCreate

OCR_CONFIDENCE_REVIEW_THRESHOLD = 0.70


class BaseRule(ABC):
    rule_id: str
    title: str
    advisory: bool = False

    @abstractmethod
    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        """
        Evaluate the rule against the application validation context.
        Returns a list of FindingCreate objects (can be empty if not applicable).
        """
        pass
