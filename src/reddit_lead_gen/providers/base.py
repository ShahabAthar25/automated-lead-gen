from abc import ABC, abstractmethod

from reddit_lead_gen.models.analysis import LeadAnalysis


class BaseLLMProvider(ABC):
    """Abstract interface for all LLM classification providers."""

    @abstractmethod
    def analyze(self, prompt: str) -> LeadAnalysis:
        """Analyzes the generated prompt and returns structured analysis."""
        pass
