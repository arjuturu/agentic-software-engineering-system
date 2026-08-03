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

    def prepare_clarification(
        self,
        workflow_id: str,
        requirement_version: int,
        current_state_version: int,
        questions: list[dict],
    ) -> tuple[dict, bool]:
        """Persist or retrieve one pending clarification and its authoritative version."""
        workflow = self.get(workflow_id)
        requirement = self._requirement(workflow_id, requirement_version)
        analysis = dict(requirement.analysis_json or {})
        existing = analysis.get("pending_clarification")
        if isinstance(existing, dict) and existing.get("status") == "PENDING":
            pending = dict(existing)
            clarification_id = pending.get("clarificationId")
            if not isinstance(clarification_id, str):
                raise ApplicationError(
                    "The clarification was not found.", "CLARIFICATION_NOT_FOUND", 404
                )
            if requirement.clarification_id not in {None, clarification_id}:
                raise ApplicationError(
                    "The clarification was not found.", "CLARIFICATION_NOT_FOUND", 404
                )
            requirement.clarification_id = clarification_id
            workflow.state_version = int(pending["stateVersion"])
            workflow.status = "WAITING_FOR_CLARIFICATION"
            workflow.current_stage = "CLARIFICATION"
            self.session.flush()
            return self._public_clarification(pending), False
        if workflow.state_version != current_state_version:
            raise ApplicationError(
                "The workflow version has changed.", "INVALID_STATE_VERSION", 409
            )
        expected_version = workflow.state_version + 1
        pending = {
            "clarificationId": f"CLR-{requirement_version}-{expected_version}",
            "stateVersion": expected_version,
            "questions": questions,
            "status": "PENDING",
        }
        analysis["pending_clarification"] = pending
        requirement.clarification_id = pending["clarificationId"]
        requirement.analysis_json = analysis
        workflow.state_version = expected_version
        workflow.status = "WAITING_FOR_CLARIFICATION"
        workflow.current_stage = "CLARIFICATION"
        self.session.flush()
        return self._public_clarification(pending), True

    def complete_clarification(
        self,
        workflow_id: str,
        requirement_version: int,
        clarification_id: str,
        expected_version: int,
        answers: list[dict[str, str]],
    ) -> tuple[int, bool]:
        """Persist answers once and advance the workflow version exactly once."""
        workflow = self.get(workflow_id)
        requirement = self._clarification(workflow_id, clarification_id)
        if requirement is None or requirement.version != requirement_version:
            raise ApplicationError(
                "The clarification was not found.", "CLARIFICATION_NOT_FOUND", 404
            )
        analysis = dict(requirement.analysis_json or {})
        record = analysis.get("pending_clarification")
        if not isinstance(record, dict) or record.get("clarificationId") != clarification_id:
            raise ApplicationError(
                "The clarification was not found.", "CLARIFICATION_NOT_FOUND", 404
            )
        if record.get("status") == "COMPLETED":
            if record.get("answers") != answers:
                raise ApplicationError(
                    "Clarification was already submitted.",
                    "CLARIFICATION_ALREADY_SUBMITTED",
                    409,
                )
            return int(record["completedStateVersion"]), False
        if (
            workflow.status != "WAITING_FOR_CLARIFICATION"
            or workflow.state_version != expected_version
            or record.get("stateVersion") != expected_version
        ):
            raise ApplicationError(
                "Clarification state does not match.", "INVALID_STATE_VERSION", 409
            )
        completed_version = expected_version + 1
        completed = {
            **record,
            "status": "COMPLETED",
            "answers": answers,
            "completedStateVersion": completed_version,
        }
        analysis["pending_clarification"] = completed
        requirement.analysis_json = analysis
        workflow.state_version = completed_version
        workflow.status = "RUNNING"
        workflow.current_stage = "REQUIREMENTS"
        self.session.flush()
        return completed_version, True

    def clarification(self, workflow_id: str, clarification_id: str) -> dict | None:
        requirement = self._clarification(workflow_id, clarification_id)
        if requirement is None or not isinstance(requirement.analysis_json, dict):
            return None
        record = requirement.analysis_json.get("pending_clarification")
        if not isinstance(record, dict) or record.get("clarificationId") != clarification_id:
            return None
        return dict(record)

    def _clarification(
        self, workflow_id: str, clarification_id: str
    ) -> WorkflowRequirement | None:
        return self.session.scalar(
            select(WorkflowRequirement).where(
                WorkflowRequirement.workflow_id == workflow_id,
                WorkflowRequirement.clarification_id == clarification_id,
            )
        )

    def _requirement(self, workflow_id: str, version: int) -> WorkflowRequirement:
        requirement = self.session.scalar(
            select(WorkflowRequirement).where(
                WorkflowRequirement.workflow_id == workflow_id,
                WorkflowRequirement.version == version,
            )
        )
        if requirement is None:
            raise ApplicationError(
                "The workflow requirement was not found.", "WORKFLOW_STATE_CONFLICT", 409
            )
        return requirement

    @staticmethod
    def _public_clarification(record: dict) -> dict:
        return {
            "clarificationId": record["clarificationId"],
            "stateVersion": record["stateVersion"],
            "questions": record["questions"],
        }

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

    def mark_tasks_completed(self, workflow_id: str, task_keys: list[str]) -> list[str]:
        if not task_keys:
            return []
        completed: list[str] = []
        tasks = self.session.scalars(
            select(WorkflowTask).where(
                WorkflowTask.workflow_id == workflow_id,
                WorkflowTask.task_key.in_(task_keys),
            )
        )
        for task in tasks:
            if task.status in {"COMPLETED", "SATISFIED"}:
                continue
            task.status = "COMPLETED"
            task.updated_at = utc_now()
            completed.append(task.task_key)
        self.session.flush()
        return completed
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
