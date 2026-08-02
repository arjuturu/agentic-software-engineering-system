from pathlib import Path

from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.tools.git_tool import GitTool
from app.tools.models import ToolStatus


def perform_rollback(
    state: dict, git: GitTool, artifacts: ArtifactService, audit: AuditService
) -> dict:
    workflow_id = state["workflow_id"]
    audit.record(workflow_id, "ROLLBACK_STARTED", "ROLLBACK")
    result = git.restore_to_commit(Path(state["repository_path"]), state.get("baseline_commit", ""))
    status = git.get_status(Path(state["repository_path"]))
    success = result.status == ToolStatus.SUCCESS and status.status == ToolStatus.SUCCESS
    record = {"success": success, "baseline_commit": state.get("baseline_commit", "")}
    reference = artifacts.write_markdown(
        workflow_id, "ROLLBACK_REPORT", "rollback-report.md", record
    )
    audit.record(
        workflow_id, "ROLLBACK_COMPLETED", "ROLLBACK", {"success": success, "artifact": reference}
    )
    return {
        "rollback_history": [*state.get("rollback_history", []), record],
        "workflow_status": "NOT_READY" if success else "SAFE_STOPPED",
        "final_release_status": "NOT_READY" if success else "SAFE_STOPPED",
        "current_stage": "ROLLBACK_COMPLETE" if success else "SAFE_STOP",
        "completed_at": __import__("app.core.time", fromlist=["utc_now"]).utc_now().isoformat(),
    }
