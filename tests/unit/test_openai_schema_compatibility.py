import pytest

from app.agents.openai_provider import build_openai_compatible_schema
from app.schemas.agents.coding import CodingOutput, RepositoryAnalysisOutput
from app.schemas.agents.design import DesignOutput
from app.schemas.agents.planning import PlanningOutput
from app.schemas.agents.release import ReleaseOutput
from app.schemas.agents.requirement import RequirementOutput
from app.schemas.agents.validation import ValidationOutput


@pytest.mark.parametrize(
    "output_model",
    [
        RequirementOutput,
        DesignOutput,
        PlanningOutput,
        RepositoryAnalysisOutput,
        CodingOutput,
        ValidationOutput,
        ReleaseOutput,
    ],
)
def test_agent_output_schema_is_openai_strict_compatible_without_http(output_model: type) -> None:
    schema = build_openai_compatible_schema(output_model)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_design_schema_declares_business_fields_for_nested_objects() -> None:
    schema = build_openai_compatible_schema(DesignOutput)
    for field_name in ("components", "api_design", "data_design", "architecture_decisions"):
        item_schema = schema["properties"][field_name]["items"]
        assert item_schema["properties"]
        assert item_schema["additionalProperties"] is False
