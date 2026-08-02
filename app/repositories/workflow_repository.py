from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.core.time import utc_now
from app.database.models import WorkflowRequirement, WorkflowRun, WorkflowTask


class WorkflowRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, workflow: WorkflowRun) -> WorkflowRun:
        self.session.add(workflow)
        self.session.flush()
        return workflow

    def get(self, workflow_id: str) -> WorkflowRun:
        item = self.session.get(WorkflowRun, workflow_id)
        if item is None:
            raise ApplicationError("The workflow was not found.", "WORKFLOW_NOT_FOUND", 404)
        return item

    def by_thread(self, thread_id: str) -> WorkflowRun:
        item = self.session.scalar(select(WorkflowRun).where(WorkflowRun.thread_id == thread_id))
        if item is None:
            raise ApplicationError("The workflow was not found.", "WORKFLOW_NOT_FOUND", 404)
        return item

    def update_state(self, workflow_id: str, state: dict) -> WorkflowRun:
        item = self.get(workflow_id)
        item.status = state.get("workflow_status", item.status)
        item.current_stage = state.get("current_stage", item.current_stage)
        item.state_version = state.get("state_version", item.state_version)
        item.baseline_commit = state.get("baseline_commit") or item.baseline_commit
        item.working_branch = state.get("working_branch") or item.working_branch
        item.updated_at = utc_now()
        if state.get("completed_at"):
            item.completed_at = utc_now()
        self.session.flush()
        return item

    def add_requirement(
        self, workflow_id: str, version: int, original: str, analysis: dict
    ) -> None:
        existing = self.session.scalar(
            select(WorkflowRequirement).where(
                WorkflowRequirement.workflow_id == workflow_id,
                WorkflowRequirement.version == version,
            )
        )
        if existing is None:
            self.session.add(
                WorkflowRequirement(
                    workflow_id=workflow_id,
                    version=version,
                    original_requirement=original,
                    normalized_requirement=analysis.get("normalized_requirement"),
                    status=analysis.get("status", "ANALYZED"),
                    analysis_json=analysis,
                )
            )

    def replace_tasks(self, workflow_id: str, plan: dict) -> None:
        for task in plan.get("tasks", []):
            key = task["task_id"]
            existing = self.session.scalar(
                select(WorkflowTask).where(
                    WorkflowTask.workflow_id == workflow_id, WorkflowTask.task_key == key
                )
            )
            if existing is None:
                self.session.add(
                    WorkflowTask(
                        workflow_id=workflow_id,
                        task_key=key,
                        title=task["title"],
                        description=task["description"],
                        task_type=task["task_type"],
                        status="PLANNED",
                        dependencies_json=task.get("dependencies", []),
                        expected_files_json=task.get("expected_files", []),
                    )
                )
