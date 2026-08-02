from typing import Protocol

from pydantic import BaseModel

from app.config import Settings
from app.core.exceptions import ApplicationError


class StructuredModelProvider(Protocol):
    def generate(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        input_payload: dict,
        output_model: type[BaseModel],
    ) -> BaseModel: ...


def create_provider(settings: Settings) -> StructuredModelProvider:
    if settings.LLM_MODE == "SCRIPTED":
        from app.agents.scripted_provider import ScriptedProvider

        return ScriptedProvider()
    if settings.LLM_MODE == "OPENAI":
        from app.agents.openai_provider import OpenAIProvider

        return OpenAIProvider(settings)
    raise ApplicationError(
        "The model provider is not configured.", "MODEL_PROVIDER_NOT_CONFIGURED", 500
    )
