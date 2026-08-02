from typing import Any

from app.core.exceptions import ApplicationError
from app.schemas.agents.common import ApprovalAction, ApprovalGate


def validate_approval_payload(
    payload: Any,
    *,
    workflow_id: str,
    approval_id: str,
    gate_type: ApprovalGate,
    state_version: int,
    allowed_actions: list[str],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ApplicationError("Invalid approval payload.", "INVALID_APPROVAL_ACTION", 400)
    required = {
        "type": "APPROVAL_DECISION",
        "workflowId": workflow_id,
        "approvalId": approval_id,
        "gateType": gate_type.value,
        "stateVersion": state_version,
    }
    if any(payload.get(key) != value for key, value in required.items()):
        raise ApplicationError("Approval state does not match.", "INVALID_STATE_VERSION", 409)
    try:
        action = ApprovalAction(payload.get("action"))
    except ValueError as exc:
        raise ApplicationError(
            "The approval action is invalid.", "INVALID_APPROVAL_ACTION", 400
        ) from exc
    if action.value not in allowed_actions:
        raise ApplicationError(
            "The approval action is not allowed.", "INVALID_APPROVAL_ACTION", 400
        )
    decided_by = payload.get("decidedBy")
    if not isinstance(decided_by, str) or not decided_by.strip():
        raise ApplicationError("The decision author is required.", "INVALID_APPROVAL_ACTION", 400)
    conditions = payload.get("conditions", [])
    if not isinstance(conditions, list) or not all(
        isinstance(condition, str) for condition in conditions
    ):
        raise ApplicationError("Approval conditions are invalid.", "INVALID_APPROVAL_ACTION", 400)
    return {
        "action": action.value,
        "comments": payload.get("comments"),
        "conditions": conditions,
        "decided_by": decided_by,
    }


def validate_clarification_payload(
    payload: Any,
    *,
    workflow_id: str,
    state_version: int,
    question_ids: list[str],
) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        raise ApplicationError(
            "Invalid clarification payload.", "INVALID_CLARIFICATION_RESPONSE", 400
        )
    if (
        payload.get("type") != "CLARIFICATION_RESPONSE"
        or payload.get("workflowId") != workflow_id
        or payload.get("stateVersion") != state_version
    ):
        raise ApplicationError("Clarification state does not match.", "INVALID_STATE_VERSION", 409)
    answers = payload.get("answers")
    if not isinstance(answers, list):
        raise ApplicationError(
            "Clarification answers are required.", "INVALID_CLARIFICATION_RESPONSE", 400
        )
    answer_ids = [answer.get("questionId") for answer in answers if isinstance(answer, dict)]
    if len(answer_ids) != len(set(answer_ids)) or set(answer_ids) != set(question_ids):
        raise ApplicationError(
            "Clarification question IDs do not match.",
            "INVALID_CLARIFICATION_RESPONSE",
            400,
        )
    normalized = []
    for answer in answers:
        value = answer.get("answer") if isinstance(answer, dict) else None
        if not isinstance(value, str) or not value.strip():
            raise ApplicationError(
                "Clarification answers cannot be empty.",
                "INVALID_CLARIFICATION_RESPONSE",
                400,
            )
        normalized.append({"question_id": answer["questionId"], "answer": value})
    return normalized
