import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import Settings
from app.core.exceptions import ApplicationError

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """Generate bounded structured outputs without exposing tools or provider details."""

    def __init__(self, settings: Settings) -> None:
        if settings.LLM_MODE != "OPENAI" or settings.OPENAI_API_KEY is None:
            raise ApplicationError(
                "The OpenAI provider is not configured.",
                "MODEL_PROVIDER_NOT_CONFIGURED",
                500,
            )
        self.model = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
            timeout=min(settings.DEFAULT_WORKFLOW_TIMEOUT_SECONDS, 120),
            max_retries=1,
        )

    def generate(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        input_payload: dict,
        output_model: type[BaseModel],
    ) -> BaseModel:
        try:
            runnable = self.model.with_structured_output(
                output_model, method="json_schema", strict=True
            )
            result = runnable.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(
                        content=json.dumps(
                            {"agent_name": agent_name, "input": input_payload},
                            sort_keys=True,
                        )
                    ),
                ]
            )
            return output_model.model_validate(result)
        except Exception as exc:
            logger.warning("model_provider=OPENAI status=FAILED error_type=%s", type(exc).__name__)
            raise ApplicationError(
                "The model provider could not produce valid structured output.",
                "MODEL_OUTPUT_INVALID",
                502,
            ) from exc
