from typing import Any

from app.core.time import utc_now
from app.orchestration.state import EngineeringWorkflowState

_STALE_BY_LEVEL = {
    "REQUIREMENT": [
        "architecture_design",
        "implementation_plan",
        "repository_analysis",
        "implementation_result",
        "validation_result",
    ],
    "DESIGN": [
        "implementation_plan",
        "repository_analysis",
        "implementation_result",
        "validation_result",
    ],
    "PLAN": ["repository_analysis", "implementation_result", "validation_result"],
}


def mark_for_replanning(state: EngineeringWorkflowState, level: str, reason: str) -> dict[str, Any]:
    """Mark downstream state stale while preserving prior evidence and versions."""
    normalized = level.upper()
    stale = list(_STALE_BY_LEVEL.get(normalized, []))
    history = list(state.get("replanning_history", []))
    history.append(
        {
            "level": normalized,
            "reason": reason,
            "occurred_at": utc_now().isoformat(),
            "stale_outputs": stale,
        }
    )
    versions: dict[str, int] = {}
    if normalized == "REQUIREMENT":
        versions["requirement_version"] = state.get("requirement_version", 1) + 1
    elif normalized == "DESIGN":
        versions["architecture_version"] = state.get("architecture_version", 1) + 1
    elif normalized == "PLAN":
        versions["plan_version"] = state.get("plan_version", 1) + 1
    return {
        "replan_level": normalized,
        "replanning_history": history,
        "stale_outputs": stale,
        "workflow_status": "REPLANNING",
        "current_stage": "REPLAN",
        **versions,
    }
