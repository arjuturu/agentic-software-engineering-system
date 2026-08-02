from app.orchestration.nodes import WorkflowNodes
from app.orchestration.routing import route_quality


def _plan(status: str = "PLANNED") -> dict:
    return {
        "tasks": [
            {
                "task_id": "TASK-001",
                "task_type": "implementation",
                "status": status,
                "dependencies": [],
            }
        ],
        "execution_order": ["TASK-001"],
    }


def test_final_validation_is_blocked_while_tasks_are_unfinished() -> None:
    nodes = WorkflowNodes.__new__(WorkflowNodes)

    result = nodes.validation_agent({"implementation_plan": _plan()})

    assert result["validation_result"]["status"] == "INCOMPLETE_IMPLEMENTATION"
    assert result["validation_result"]["unfinished_task_ids"] == ["TASK-001"]
    assert route_quality(result) == "coding_agent"


def test_missing_endpoint_criteria_are_not_implemented_and_architecture_fails() -> None:
    state = {
        "approved_requirement": {
            "acceptance_criteria": [
                "POST /api/v1/urls creates a short URL.",
                "GET /{short_code} redirects to the original URL.",
            ]
        }
    }
    output = {
        "acceptance_criteria_results": [],
        "architecture_compliance": True,
        "status": "VALIDATION_PASSED",
        "release_recommendation": "READY",
        "retry_recommended": False,
        "replan_recommended": False,
        "failure_category": None,
    }

    result = WorkflowNodes._normalize_final_validation(
        state, output, {"status": "FAIL"}
    )

    assert [item["status"] for item in result["acceptance_criteria_results"]] == [
        "NOT_IMPLEMENTED",
        "NOT_IMPLEMENTED",
    ]
    assert result["architecture_compliance"] is False
    assert result["status"] == "VALIDATION_FAILED"
    assert result["failure_category"] == "ARCHITECTURE_MISMATCH"


def test_criterion_without_evidence_is_not_tested() -> None:
    state = {"approved_requirement": {"acceptance_criteria": ["Behavior is verified."]}}
    output = {
        "acceptance_criteria_results": [],
        "architecture_compliance": True,
        "status": "VALIDATION_PASSED",
        "release_recommendation": "READY",
        "retry_recommended": False,
        "replan_recommended": False,
        "failure_category": None,
    }

    result = WorkflowNodes._normalize_final_validation(
        state, output, {"status": "NOT_APPLICABLE"}
    )

    assert result["acceptance_criteria_results"][0]["status"] == "NOT_TESTED"
    assert result["architecture_compliance"] is False
