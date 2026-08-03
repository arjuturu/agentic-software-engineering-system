from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_default_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.APP_NAME == "Agentic Software Engineering System"
    assert settings.APP_ENV == "local"
    assert settings.DATABASE_URL == "sqlite:///./data/application.db"
    assert settings.SHORT_CODE_LENGTH == 7
    assert settings.WORKSPACE_ROOT == Path("workspace").resolve()
    assert settings.ARTIFACT_ROOT == Path("generated_artifacts").resolve()
    assert settings.MAX_SCAN_FILES == 2000
    assert settings.MAX_SCAN_FILE_BYTES == 1048576
    assert settings.MAX_EDIT_FILE_BYTES == 1048576
    assert settings.MAX_COMMAND_OUTPUT_BYTES == 1048576
    assert settings.ENABLE_GIT_WRITES is True
    assert settings.ENABLE_EXTERNAL_NETWORK is False
    assert settings.OPENAI_MODEL == "gpt-5.6-terra"
    assert settings.OPENAI_REASONING_EFFORT == "medium"


def test_invalid_short_code_length() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SHORT_CODE_LENGTH=0)


def test_invalid_openai_reasoning_effort() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, OPENAI_REASONING_EFFORT="extreme")
