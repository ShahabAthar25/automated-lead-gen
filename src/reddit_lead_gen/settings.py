import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def load_toml_config(config_path: str = "config.toml") -> Dict[str, Any]:
    path = Path(config_path)
    if path.exists():
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


# Sub models for settings


class AppConfig(BaseModel):
    name: str = "reddit-lead-gen"
    log_level: str = "INFO"


class TargetSubredditsConfig(BaseModel):
    active: List[str] = ["forhire", "freelance_forhire", "python", "Pakfreelancers"]


class PollingConfig(BaseModel):
    poll_tick_seconds: int = 5
    default_base_interval: int = 120
    default_min_interval: int = 45
    default_max_interval: int = 900


class PipelineConfig(BaseModel):
    min_lead_score: float = 0.70
    candidate_keywords: List[str] = ["hiring", "budget", "looking for", "developer"]


class UserProfileConfig(BaseModel):
    primary_role: str = "Full-Stack & Automation Developer"
    target_services: List[str] = ["Web Scraping", "Python Automation", "Backend APIs"]
    dealbreakers: List[str] = []


class DatabaseConfig(BaseModel):
    database_url: str = "sqlite:///leads.db"


class SubredditOverrideConfig(BaseModel):
    base_interval: int = 120
    min_interval: int = 45
    max_interval: int = 900


# Main setting module


class Settings(BaseSettings):
    reddit_feed_token: str
    reddit_username: str

    gemini_api_key: str
    discord_webhook_url: str

    # Operational Sections (populated via config.toml)
    app: AppConfig = Field(default_factory=AppConfig)
    target_subreddits: TargetSubredditsConfig = Field(
        default_factory=TargetSubredditsConfig
    )
    polling: PollingConfig = Field(default_factory=PollingConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    user_profile: UserProfileConfig = Field(default_factory=UserProfileConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    subreddits: Dict[str, SubredditOverrideConfig] = Field(default_factory=dict)

    # Pydantic reads your .env file automatically here:
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @classmethod
    def load(cls, config_path: str = "config.toml") -> "Settings":
        """Factory method that merges config.toml data into Pydantic models."""
        toml_data = load_toml_config(config_path)
        return cls(**toml_data)


# Instantiate once
settings = Settings.load()
