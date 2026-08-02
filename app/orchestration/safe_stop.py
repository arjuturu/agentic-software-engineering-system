from app.core.time import utc_now
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService


def safe_stop_workflow(state: dict, artifacts: ArtifactService, audit: AuditService) -> dict:
    reason = state.get(
        "last_error", {"code": "SAFE_STOPPED", "message": "The workflow stopped safely."}
    )
    report = {
        "reason": reason,
        "recovery_recommendation": "Review governed evidence before starting a new workflow.",
    }
    reference = artifacts.write_markdown(
        state["workflow_id"], "SAFE_STOP_REPORT", "safe-stop-report.md", report
    )
    audit.record(
        state["workflow_id"],
        "SAFE_STOP_TRIGGERED",
        "SAFE_STOP",
        {"error_code": reason.get("code", "SAFE_STOPPED"), "artifact": reference},
    )
    return {
        "workflow_status": "SAFE_STOPPED",
        "final_release_status": "SAFE_STOPPED",
        "current_stage": "SAFE_STOP",
        "artifact_references": {**state.get("artifact_references", {}), "safe_stop": reference},
        "completed_at": utc_now().isoformat(),
    }
