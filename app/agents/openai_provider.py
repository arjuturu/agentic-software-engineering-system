import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.core.exceptions import ApplicationError

logger = logging.getLogger(__name__)


def build_openai_compatible_schema(output_model: type[BaseModel]) -> dict[str, Any]:
    """Build and locally validate the strict schema sent to native structured output."""
    schema = convert_to_openai_tool(output_model, strict=True)["function"]["parameters"]
    _validate_strict_schema(schema)
    return schema


def _validate_strict_schema(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        if value.get("type") == "object":
            properties = value.get("properties")
            if not isinstance(properties, dict) or not properties:
                raise ValueError(f"Strict structured output requires fields at {path}.")
            if value.get("additionalProperties") is not False:
                raise ValueError(f"Strict object must forbid additional properties at {path}.")
            required = value.get("required")
            if not isinstance(required, list) or set(required) != set(properties):
                raise ValueError(f"Strict object fields must all be required at {path}.")
        for key, nested in value.items():
            _validate_strict_schema(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_strict_schema(nested, f"{path}[{index}]")


def _response_metadata(raw: object | None) -> tuple[str | None, int | None, int | None]:
    metadata = getattr(raw, "response_metadata", None) or {}
    usage = getattr(raw, "usage_metadata", None) or metadata.get("token_usage", {}) or {}
    finish_reason = metadata.get("finish_reason")
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    return finish_reason, input_tokens, output_tokens


def _sanitized_diagnostics(
    exc: Exception,
    *,
    agent_name: str,
    request_made: bool,
    raw: object | None,
) -> dict[str, Any]:
    field_paths: list[str] = []
    validation_error_types: list[str] = []
    if isinstance(exc, ValidationError):
        for error in exc.errors(include_input=False, include_url=False):
            field_paths.append(".".join(str(part) for part in error.get("loc", ())))
            validation_error_types.append(str(error.get("type", "validation_error")))
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error_body = body.get("error", body)
        if isinstance(error_body, dict):
            if error_body.get("param"):
                field_paths.append(str(error_body["param"]))
            if error_body.get("type"):
                validation_error_types.append(str(error_body["type"]))
            elif error_body.get("code"):
                validation_error_types.append(str(error_body["code"]))
    finish_reason, input_tokens, output_tokens = _response_metadata(raw)
    return {
        "agent_name": agent_name,
        "exception_class": type(exc).__name__,
        "field_paths": sorted(set(filter(None, field_paths))),
        "validation_error_types": sorted(set(validation_error_types)),
        "finish_reason": finish_reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "http_request_made": request_made,
    }


class OpenAIProvider:
    """Generate bounded structured outputs without exposing tools or provider details."""

    def __init__(self, settings: Settings) -> None:
        if settings.LLM_MODE != "OPENAI" or settings.OPENAI_API_KEY is None:
            raise ApplicationError(
                "The OpenAI provider is not configured.",
                "MODEL_PROVIDER_NOT_CONFIGURED",
                500,
            )
        model_options: dict[str, Any] = {
            "model": settings.OPENAI_MODEL,
            "reasoning_effort": settings.OPENAI_REASONING_EFFORT,
            "api_key": settings.OPENAI_API_KEY,
            "timeout": min(settings.DEFAULT_WORKFLOW_TIMEOUT_SECONDS, 120),
            "max_retries": 1,
            "max_tokens": settings.OPENAI_MAX_OUTPUT_TOKENS,
        }
        if not settings.OPENAI_MODEL.startswith("gpt-5.6"):
            model_options["temperature"] = settings.OPENAI_TEMPERATURE
        self.model = ChatOpenAI(
            **model_options,
        )

    def generate(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        input_payload: dict,
        output_model: type[BaseModel],
    ) -> BaseModel:
        request_made = False
        raw: object | None = None
        try:
            build_openai_compatible_schema(output_model)
            runnable = self.model.with_structured_output(
                output_model,
                method="json_schema",
                strict=True,
                include_raw=True,
            )
            request_made = True
            envelope = runnable.invoke(
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
            raw = envelope.get("raw") if isinstance(envelope, dict) else None
            parsing_error = envelope.get("parsing_error") if isinstance(envelope, dict) else None
            if isinstance(parsing_error, Exception):
                raise parsing_error
            parsed = envelope.get("parsed") if isinstance(envelope, dict) else envelope
            return output_model.model_validate(parsed)
        except Exception as exc:
            diagnostics = _sanitized_diagnostics(
                exc,
                agent_name=agent_name,
                request_made=request_made,
                raw=raw,
            )
            logger.warning(
                "model_provider=OPENAI status=FAILED agent=%s error_type=%s request_made=%s",
                agent_name,
                diagnostics["exception_class"],
                request_made,
            )
            raise ApplicationError(
                "The model provider could not produce valid structured output.",
                "MODEL_OUTPUT_INVALID",
                502,
                details=diagnostics,
            ) from exc
