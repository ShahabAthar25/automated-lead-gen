from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    reddit_feed_token: str
    reddit_username: str
    
    gemini_api_key: str
    discord_webhook_url: str

    database_url: str = "sqlite:///leads.db"

    # Pydantic reads your .env file automatically here:
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Instantiate once
settings = Settings()
