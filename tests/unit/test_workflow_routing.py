from app.orchestration.routing import route_quality, route_requirement


def test_routing_is_deterministic() -> None:
    assert (
        route_requirement({"requirement_analysis": {"status": "CLARIFICATION_REQUIRED"}})
        == "prepare_clarification"
    )
    assert (
        route_quality({"validation_result": {"status": "VALIDATION_PASSED"}})
        == "documentation_release_agent"
    )
    assert (
        route_quality(
            {
                "validation_result": {
                    "status": "VALIDATION_FAILED",
                    "failure_category": "IMPLEMENTATION_DEFECT",
                }
            }
        )
        == "retry_router"
    )
