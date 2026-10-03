from google.genai.errors import APIError as GeminiAPIError
from groq import APIStatusError as GroqAPIStatusError


def extract_status_code(exc: Exception) -> int | None:
    """Extracts HTTP status code from supported provider exceptions."""
    if isinstance(exc, GroqAPIStatusError):
        return exc.status_code
    if isinstance(exc, GeminiAPIError):
        return exc.code
    # Fallback checking common attributes on generic exceptions
    if hasattr(exc, "status_code"):
        return getattr(exc, "status_code")
    if hasattr(exc, "code") and isinstance(getattr(exc, "code"), int):
        return getattr(exc, "code")
    return None
