from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    MAX_SCAN_FILES: int = Field(default=2000, gt=0)
    MAX_SCAN_FILE_BYTES: int = Field(default=1048576, gt=0)
    MAX_EDIT_FILE_BYTES: int = Field(default=1048576, gt=0)
    MAX_COMMAND_OUTPUT_BYTES: int = Field(default=1048576, gt=0)
    ENABLE_GIT_WRITES: bool = True
    ENABLE_EXTERNAL_NETWORK: bool = False
    LOG_LEVEL: str = "INFO"

    LLM_MODE: Literal["SCRIPTED", "OPENAI"] = "SCRIPTED"
    OPENAI_API_KEY: SecretStr | None = None
    OPENAI_MODEL: str = ""
    OPENAI_TEMPERATURE: float = Field(default=0, ge=0, le=2)
    OPENAI_MAX_OUTPUT_TOKENS: int = Field(default=2500, gt=0)
    REQUIREMENT_AGENT_MAX_RETRIES: int = Field(default=1, ge=0)
    DESIGN_AGENT_MAX_RETRIES: int = Field(default=1, ge=0)
    PLANNING_AGENT_MAX_RETRIES: int = Field(default=1, ge=0)
    CODING_AGENT_MAX_RETRIES: int = Field(default=2, ge=0)
    VALIDATION_AGENT_MAX_RETRIES: int = Field(default=1, ge=0)
    DEFAULT_WORKFLOW_TIMEOUT_SECONDS: int = Field(default=300, gt=0)

    @field_validator("WORKSPACE_ROOT", "ARTIFACT_ROOT", mode="after")
    @classmethod
    def resolve_directory(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @model_validator(mode="after")
    def validate_model_provider(self) -> "Settings":
        if self.LLM_MODE == "OPENAI":
            api_key = (
                self.OPENAI_API_KEY.get_secret_value().strip()
                if self.OPENAI_API_KEY is not None
                else ""
            )
            if not api_key or not self.OPENAI_MODEL.strip():
                raise ValueError("OPENAI mode requires an API key and model.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
