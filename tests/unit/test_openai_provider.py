from typing import Any

import pytest
from pydantic import BaseModel

from app.agents.openai_provider import OpenAIProvider
from app.config import Settings
from app.core.exceptions import ApplicationError
from app.schemas.agents.design import DesignOutput


class _RawResponse:
    response_metadata = {"finish_reason": "stop"}
    usage_metadata = {"input_tokens": 42, "output_tokens": 7}


class _Runnable:
    def invoke(self, messages: list) -> dict:
        assert messages
        return {
            "raw": _RawResponse(),
            "parsed": {"architecture_summary": "incomplete"},
            "parsing_error": None,
        }


class _Model:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def with_structured_output(self, output_model: type[BaseModel], **kwargs) -> _Runnable:
        self.calls.append({"output_model": output_model, **kwargs})
        return _Runnable()


def test_provider_configures_terra_with_explicit_reasoning_without_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class ConstructorOnlyModel:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("app.agents.openai_provider.ChatOpenAI", ConstructorOnlyModel)
    settings = Settings(
        _env_file=None,
        LLM_MODE="OPENAI",
        OPENAI_API_KEY="test-placeholder",
    )

    OpenAIProvider(settings)

    assert captured["model"] == "gpt-5.6-terra"
    assert captured["reasoning_effort"] == "medium"
    assert "temperature" not in captured
    assert captured["max_tokens"] == 2500


def test_provider_uses_native_json_schema_and_sanitizes_validation_failure() -> None:
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.model = _Model()
    with pytest.raises(ApplicationError) as raised:
        provider.generate(
            agent_name="DESIGN_AGENT",
            system_prompt="safe",
            input_payload={"workflow_id": "WF-TEST"},
            output_model=DesignOutput,
        )
    call = provider.model.calls[0]
    assert call == {
        "output_model": DesignOutput,
        "method": "json_schema",
        "strict": True,
        "include_raw": True,
    }
    details = raised.value.details
    assert details["exception_class"] == "ValidationError"
    assert details["http_request_made"] is True
    assert details["finish_reason"] == "stop"
    assert details["input_tokens"] == 42
    assert details["output_tokens"] == 7
    assert "components" in details["field_paths"]
    assert "raw" not in details


class _IncompatibleOutput(BaseModel):
    items: list[dict[str, Any]]


def test_incompatible_schema_fails_before_http_request() -> None:
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.model = _Model()
    with pytest.raises(ApplicationError) as raised:
        provider.generate(
            agent_name="TEST_AGENT",
            system_prompt="safe",
            input_payload={},
            output_model=_IncompatibleOutput,
        )
    assert provider.model.calls == []
    assert raised.value.details["exception_class"] == "ValueError"
    assert raised.value.details["http_request_made"] is False
