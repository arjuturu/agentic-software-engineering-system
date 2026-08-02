import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.base import PromptLoader
from app.core.exceptions import ApplicationError
from app.orchestration.state import EngineeringWorkflowState
from app.schemas.agents.requirement import RequirementOutput


def test_agent_schema_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        RequirementOutput.model_validate(
            {
                "normalized_requirement": "x",
                "functional_requirements": [],
                "non_functional_requirements": [],
                "assumptions": [],
                "ambiguities": [],
                "clarification_questions": [],
                "acceptance_criteria": [],
                "risks": [],
                "material_ambiguity": False,
                "risk_level": "LOW",
                "status": "INVENTED",
            }
        )


def test_state_is_json_serializable() -> None:
    state: EngineeringWorkflowState = {
        "workflow_id": "WF-TEST",
        "retry_counts": {"coding": 1},
        "approval_history": [],
    }
    assert json.loads(json.dumps(state))["workflow_id"] == "WF-TEST"


def test_prompt_loader_blocks_traversal(tmp_path: Path) -> None:
    loader = PromptLoader(tmp_path)
    with pytest.raises(ApplicationError) as error:
        loader.load("../requirement-agent.md")
    assert error.value.error_code == "PROMPT_PATH_BLOCKED"
