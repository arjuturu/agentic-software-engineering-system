from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import ApplicationError
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.audit_repository import AuditRepository


class ApprovalService:
    ACTIONS = ["APPROVE", "APPROVE_WITH_CONDITIONS", "REQUEST_CHANGES", "REJECT"]

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def request(self, workflow_id: str, gate_type: str, state_version: int) -> dict:
        with self.sessions.begin() as session:
            repository = ApprovalRepository(session)
            item = repository.request(workflow_id, gate_type, state_version, self.ACTIONS)
            AuditRepository(session).add(
                workflow_id,
                "APPROVAL_REQUESTED",
                gate_type,
                {"approval_id": item.id, "gate_type": gate_type, "state_version": state_version},
            )
            return {
                "approvalId": item.id,
                "gateType": gate_type,
                "stateVersion": state_version,
                "allowedActions": list(item.allowed_actions_json),
            }

    def validate_for_resume(self, workflow_id: str, approval_id: str, payload: dict) -> None:
        with self.sessions() as session:
            item = ApprovalRepository(session).get(approval_id)
            if item.workflow_id != workflow_id:
                raise ApplicationError("The approval was not found.", "APPROVAL_NOT_FOUND", 404)
            if item.status != "PENDING":
                raise ApplicationError(
                    "The approval was already completed.", "APPROVAL_ALREADY_COMPLETED", 409
                )
            if payload["gateType"] != item.gate_type:
                raise ApplicationError(
                    "The approval gate does not match.", "WORKFLOW_STATE_CONFLICT", 409
                )
            if payload["stateVersion"] != item.state_version:
                raise ApplicationError(
                    "The workflow version has changed.", "INVALID_STATE_VERSION", 409
                )
            if payload["action"] not in item.allowed_actions_json:
                raise ApplicationError(
                    "The approval action is not allowed.", "INVALID_APPROVAL_ACTION", 400
                )

    def decide(self, workflow_id: str, approval_id: str, payload: dict) -> dict:
        with self.sessions.begin() as session:
            repository = ApprovalRepository(session)
            item = repository.get(approval_id)
            decision = repository.decide(item, payload)
            AuditRepository(session).add(
                workflow_id,
                "APPROVAL_DECIDED",
                item.gate_type,
                {"approval_id": item.id, "action": decision.action},
                actor_type="HUMAN",
                actor_id=decision.decided_by,
            )
            return {"approval_id": item.id, "action": decision.action}
