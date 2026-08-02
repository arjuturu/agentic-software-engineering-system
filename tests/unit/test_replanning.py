from app.orchestration.replanning import mark_for_replanning


def test_replanning_marks_downstream_outputs_stale() -> None:
    result = mark_for_replanning(
        {"architecture_version": 1, "replanning_history": []}, "DESIGN", "Mismatch"
    )
    assert result["architecture_version"] == 2
    assert "implementation_plan" in result["stale_outputs"]
    assert result["workflow_status"] == "REPLANNING"
