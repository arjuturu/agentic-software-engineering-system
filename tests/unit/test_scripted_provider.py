import pytest

from app.agents.scripted_provider import ScriptedProvider
from app.schemas.agents.coding import CodingOutput, RepositoryAnalysisOutput
from app.schemas.agents.design import DesignOutput
from app.schemas.agents.planning import PlanningOutput
from app.schemas.agents.release import ReleaseOutput
from app.schemas.agents.requirement import RequirementOutput
from app.schemas.agents.validation import ValidationOutput


@pytest.mark.parametrize(
    "agent,model",
    [
        ("REQUIREMENT_AGENT", RequirementOutput),
        ("DESIGN_AGENT", DesignOutput),
        ("PLANNING_AGENT", PlanningOutput),
        ("REPOSITORY_AGENT", RepositoryAnalysisOutput),
        ("CODING_AGENT", CodingOutput),
        ("VALIDATION_AGENT", ValidationOutput),
        ("DOCUMENTATION_RELEASE_AGENT", ReleaseOutput),
    ],
)
def test_scripted_provider_returns_typed_output(agent, model) -> None:
    payload = {
        "workflow_id": "WF-TEST",
        "scenario_type": "GREENFIELD",
        "scripted_scenario": "HAPPY_PATH",
        "retry_number": 0,
        "original_requirement": "Create a service",
        "clarification_answers": [],
        "approved_requirement": {},
        "architecture_design": {},
        "deterministic_scan": {},
        "implementation_plan": {},
        "repository_analysis": {},
        "file_hashes": {},
        "command_results": [{"status": "SUCCESS"}],
        "implementation_result": {},
        "validation_result": {"status": "VALIDATION_PASSED"},
        "documentation_draft": {},
        "context": {},
    }
    result = ScriptedProvider().generate(
        agent_name=agent, system_prompt="safe", input_payload=payload, output_model=model
    )
    assert isinstance(result, model)
