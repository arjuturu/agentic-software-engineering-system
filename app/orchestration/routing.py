from app.orchestration.state import EngineeringWorkflowState


def route_requirement(state: EngineeringWorkflowState) -> str:
    status = state.get("requirement_analysis", {}).get("status")
    return {
        "CLARIFICATION_REQUIRED": "prepare_clarification",
        "READY_FOR_APPROVAL": "prepare_requirement_approval",
        "REJECTED_AS_UNSAFE": "safe_stop",
    }.get(status, "safe_stop")


def route_design_agent(state: EngineeringWorkflowState) -> str:
    error = state.get("last_error", {})
    if error:
        return "design_agent" if error.get("retry_allowed") else "safe_stop"
    return "design_validation"


def route_requirement_approval(state: EngineeringWorkflowState) -> str:
    return {
        "APPROVE": "design_agent",
        "APPROVE_WITH_CONDITIONS": "design_agent",
        "REQUEST_CHANGES": "requirement_agent",
        "REJECT": "safe_stop",
    }.get(state.get("last_approval_action", ""), "safe_stop")


def route_architecture_approval(state: EngineeringWorkflowState) -> str:
    return {
        "APPROVE": "workspace_setup",
        "APPROVE_WITH_CONDITIONS": "workspace_setup",
        "REQUEST_CHANGES": "design_agent",
        "REJECT": "safe_stop",
    }.get(state.get("last_approval_action", ""), "safe_stop")


def route_quality(state: EngineeringWorkflowState) -> str:
    validation = state.get("validation_result", {})
    status = validation.get("status")
    category = validation.get("failure_category")
    if status == "VALIDATION_PASSED":
        return "documentation_release_agent"
    if category == "IMPLEMENTATION_DEFECT":
        return "retry_router"
    if category == "REQUIREMENT_AMBIGUITY":
        return "replan"
    if category == "ARCHITECTURE_MISMATCH":
        return "replan"
    if category in {"POLICY_VIOLATION", "CRITICAL_SECURITY_FAILURE"}:
        return "safe_stop"
    return "rollback"


def route_retry(state: EngineeringWorkflowState) -> str:
    return "coding_agent" if state.get("last_error", {}).get("retry_allowed") else "rollback"


def route_replan(state: EngineeringWorkflowState) -> str:
    return {
        "REQUIREMENT": "requirement_agent",
        "DESIGN": "design_agent",
        "PLAN": "planning_agent",
    }.get(state.get("replan_level", ""), "safe_stop")


def route_release_approval(state: EngineeringWorkflowState) -> str:
    return {
        "APPROVE": "finalize_ready",
        "APPROVE_WITH_CONDITIONS": "finalize_ready_with_conditions",
        "REQUEST_CHANGES": "replan",
        "REJECT": "rollback",
    }.get(state.get("last_approval_action", ""), "safe_stop")
