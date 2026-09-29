from typing import Tuple, override

from google import genai
from google.genai import types

from reddit_lead_gen.models.analysis import LeadAnalysis
from reddit_lead_gen.providers.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    @override
    def analyze(self, prompt: str) -> Tuple[float, LeadAnalysis | None]:
        response = self.client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LeadAnalysis,
                temperature=0.1,
            ),
        )

        # Parse returned structured JSON into Pydantic model
        analysis = LeadAnalysis.model_validate_json(response.text)

        # If author is NOT hiring, force score to 0
        final_score = analysis.score if analysis.is_hiring else 0.0
        return final_score, analysis
