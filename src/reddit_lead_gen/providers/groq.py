import json
import logging
from typing import Tuple, override

from groq import AsyncGroq

from reddit_lead_gen.models.analysis import LeadAnalysis
from reddit_lead_gen.providers.base import BaseLLMProvider


class GroqProvider(BaseLLMProvider):
    name: str = "Groq"

    def __init__(self, api_key: str):
        self.client = AsyncGroq(api_key=api_key)

    @override
    async def analyze(self, prompt: str) -> Tuple[float, LeadAnalysis | None]:
        schema_json = json.dumps(LeadAnalysis.model_json_schema(), indent=2)

        system_instruction = (
            "You are an expert lead classifier.\n"
            "Analyze the post and output your evaluation ONLY as a raw, valid JSON object.\n"
            "Do NOT wrap the JSON in markdown code blocks (e.g. do NOT use ```json ... ```).\n"
            "Do NOT include any commentary or introductory text before or after the JSON.\n\n"
            f"Required Output Schema:\n{schema_json}"
        )

        response = await self.client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if not content:
            logging.warning("Groq returned an empty response.")
            return 0.0, None

        # Clean potential markdown fences if the model still adds them
        clean_content = content.strip()
        if clean_content.startswith("```"):
            clean_content = clean_content.split("```")[1]
            if clean_content.startswith("json"):
                clean_content = clean_content[4:]
            clean_content = clean_content.strip()

        analysis = LeadAnalysis.model_validate_json(clean_content)
        final_score = analysis.score if analysis.is_hiring else 0.0

        return final_score, analysis
