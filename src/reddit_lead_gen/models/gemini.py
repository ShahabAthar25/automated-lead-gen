from pydantic import BaseModel, Field


class LeadAnalysis(BaseModel):
    is_hiring: bool = Field(
        description="True ONLY if the author is seeking to hire/pay someone. False if they are offering their own services (For Hire)."
    )
    score: float = Field(
        description="Confidence score between 0.0 (not a lead) and 1.0 (perfect lead match)."
    )
    extracted_budget: str | None = Field(
        default=None, 
        description="Extracted budget if mentioned (e.g., '$500', '$50/hr'), else None."
    )
    matched_skills: list[str] = Field(
        default_factory=list, 
        description="Technologies or skills requested in the post."
    )
    reasoning: str = Field(
        description="1-sentence explanation of why this post was or was not classified as a good lead."
    )
