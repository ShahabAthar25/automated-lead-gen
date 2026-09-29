from groq import Groq

from reddit_lead_gen.settings import settings


def list_groq_models() -> list[str]:
    """Fetches and returns active model IDs from Groq API."""
    client = Groq(api_key=settings.groq_api_key)
    models_page = client.models.list()

    # Access model metadata objects
    return [model.id for model in models_page.data]


if __name__ == "__main__":
    active_models = list_groq_models()
    print("Available Groq Models:")
    for model_id in sorted(active_models):
        print(f"- {model_id}")
