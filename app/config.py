from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    APP_NAME: str = "Agentic Software Engineering System"
    APP_ENV: str = "local"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./data/application.db"
    LANGGRAPH_DATABASE_URL: str = "sqlite:///./data/langgraph_checkpoints.db"
    WORKSPACE_ROOT: Path = Path("./workspace")
    ARTIFACT_ROOT: Path = Path("./generated_artifacts")
    SHORT_URL_BASE: str = "http://localhost:8000"
    SHORT_CODE_LENGTH: int = Field(default=7, gt=0)
    MAX_AGENT_RETRIES: int = 2
    MAX_COMMAND_SECONDS: int = 120
    ENABLE_GIT_WRITES: bool = True
    ENABLE_EXTERNAL_NETWORK: bool = False
    LOG_LEVEL: str = "INFO"

    @field_validator("WORKSPACE_ROOT", "ARTIFACT_ROOT", mode="after")
    @classmethod
    def resolve_directory(cls, value: Path) -> Path:
        return value.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
