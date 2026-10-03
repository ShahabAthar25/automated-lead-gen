from abc import ABC, abstractmethod
from typing import Tuple

from reddit_lead_gen.models.analysis import LeadAnalysis


class BaseLLMProvider(ABC):
    """Abstract interface for all LLM classification providers."""

    name: str

    @abstractmethod
    async def analyze(self, prompt: str) -> Tuple[float, LeadAnalysis | None]:
        """Analyzes the generated prompt and returns structured analysis."""
        pass
