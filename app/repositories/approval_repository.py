from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.core.identifiers import new_approval_id
from app.core.time import utc_now
from app.database.models import ApprovalDecision, ApprovalRequest


class ApprovalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def pending(self, workflow_id: str, gate_type: str) -> ApprovalRequest | None:
        return self.session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.workflow_id == workflow_id,
                ApprovalRequest.gate_type == gate_type,
                ApprovalRequest.status == "PENDING",
            )
        )

    def request(
        self, workflow_id: str, gate_type: str, version: int, actions: list[str]
    ) -> ApprovalRequest:
        item = self.pending(workflow_id, gate_type)
        if item is None:
            item = ApprovalRequest(
                id=new_approval_id(),
                workflow_id=workflow_id,
                gate_type=gate_type,
                state_version=version,
                status="PENDING",
                allowed_actions_json=actions,
            )
            self.session.add(item)
            self.session.flush()
        return item

    def get(self, approval_id: str) -> ApprovalRequest:
        item = self.session.get(ApprovalRequest, approval_id)
        if item is None:
            raise ApplicationError("The approval was not found.", "APPROVAL_NOT_FOUND", 404)
        return item

    def decide(self, item: ApprovalRequest, payload: dict) -> ApprovalDecision:
        existing = self.session.scalar(
            select(ApprovalDecision).where(ApprovalDecision.approval_id == item.id)
        )
        if existing is not None:
            raise ApplicationError(
                "The approval was already completed.", "APPROVAL_ALREADY_COMPLETED", 409
            )
        decision = ApprovalDecision(
            approval_id=item.id,
            workflow_id=item.workflow_id,
            action=payload["action"],
            comments=payload.get("comments"),
            conditions_json=payload.get("conditions", []),
            decided_by=payload["decidedBy"],
        )
        item.status = "COMPLETED"
        item.completed_at = utc_now()
        self.session.add(decision)
        self.session.flush()
        return decision
