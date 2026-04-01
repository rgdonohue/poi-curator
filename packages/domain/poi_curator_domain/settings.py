from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POI_CURATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://poi_curator:poi_curator@localhost:5432/poi_curator"
    default_region: str = "santa-fe"
    scoring_profile_version: str = "v0"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_timeout_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
