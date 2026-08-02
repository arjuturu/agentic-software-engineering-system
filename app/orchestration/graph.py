from langgraph.graph import END, START, StateGraph

from app.orchestration.nodes import WorkflowNodes
from app.orchestration.routing import (
    route_architecture_approval,
    route_quality,
    route_release_approval,
    route_replan,
    route_requirement,
    route_requirement_approval,
    route_retry,
)
from app.orchestration.state import EngineeringWorkflowState


def build_workflow_graph(nodes: WorkflowNodes, checkpointer):
    builder = StateGraph(EngineeringWorkflowState)
    methods = {
        "start": nodes.start,
        "requirement_agent": nodes.requirement_agent,
        "prepare_clarification": nodes.prepare_clarification,
        "clarification_gate": nodes.clarification_gate,
        "prepare_requirement_approval": nodes.prepare_requirement_approval,
        "requirement_approval_gate": nodes.requirement_approval_gate,
        "design_agent": nodes.design_agent,
        "design_validation": nodes.design_validation,
        "planning_agent": nodes.planning_agent,
        "plan_validation": nodes.plan_validation,
        "prepare_architecture_approval": nodes.prepare_architecture_approval,
        "architecture_approval_gate": nodes.architecture_approval_gate,
        "workspace_setup": nodes.workspace_setup,
        "repository_analysis": nodes.repository_analysis,
        "repository_policy_validation": nodes.repository_policy_validation,
        "git_checkpoint": nodes.git_checkpoint,
        "coding_agent": nodes.coding_agent,
        "change_policy_validation": nodes.change_policy_validation,
        "prepare_high_risk_approval": nodes.prepare_high_risk_approval,
        "high_risk_approval_gate": nodes.high_risk_approval_gate,
        "apply_changes": nodes.apply_changes,
        "parallel_start": nodes.parallel_start,
        "validation_agent": nodes.validation_agent,
        "documentation_draft": nodes.documentation_draft,
        "validation_join": nodes.validation_join,
        "failure_classifier": nodes.failure_classifier,
        "retry_router": nodes.retry_router,
        "replan": nodes.replan,
        "rollback": nodes.rollback,
        "safe_stop": nodes.safe_stop,
        "documentation_release_agent": nodes.documentation_release_agent,
        "prepare_release_approval": nodes.prepare_release_approval,
        "release_approval_gate": nodes.release_approval_gate,
        "finalize_ready": nodes.finalize_ready,
        "finalize_ready_with_conditions": nodes.finalize_ready_with_conditions,
        "finalize_not_ready": nodes.finalize_not_ready,
    }
    for name, method in methods.items():
        builder.add_node(name, method)

    builder.add_edge(START, "start")
    builder.add_edge("start", "requirement_agent")
    builder.add_conditional_edges("requirement_agent", route_requirement)
    builder.add_edge("prepare_clarification", "clarification_gate")
    builder.add_edge("clarification_gate", "requirement_agent")
    builder.add_edge("prepare_requirement_approval", "requirement_approval_gate")
    builder.add_conditional_edges("requirement_approval_gate", route_requirement_approval)
    builder.add_edge("design_agent", "design_validation")
    builder.add_conditional_edges(
        "design_validation",
        lambda state: "safe_stop" if state.get("last_error") else "planning_agent",
    )
    builder.add_edge("planning_agent", "plan_validation")
    builder.add_conditional_edges(
        "plan_validation",
        lambda state: "safe_stop" if state.get("last_error") else "prepare_architecture_approval",
    )
    builder.add_edge("prepare_architecture_approval", "architecture_approval_gate")
    builder.add_conditional_edges("architecture_approval_gate", route_architecture_approval)
    builder.add_edge("workspace_setup", "repository_analysis")
    builder.add_edge("repository_analysis", "repository_policy_validation")
    builder.add_conditional_edges(
        "repository_policy_validation",
        lambda state: "safe_stop" if state.get("last_error") else "git_checkpoint",
    )
    builder.add_conditional_edges(
        "git_checkpoint",
        lambda state: "safe_stop" if state.get("last_error") else "coding_agent",
    )
    builder.add_edge("coding_agent", "change_policy_validation")
    builder.add_conditional_edges(
        "change_policy_validation",
        lambda state: (
            "safe_stop"
            if state.get("last_error")
            else "prepare_high_risk_approval"
            if state.get("code_change_plan", {}).get("high_risk_change")
            else "apply_changes"
        ),
    )
    builder.add_edge("prepare_high_risk_approval", "high_risk_approval_gate")
    builder.add_conditional_edges(
        "high_risk_approval_gate",
        lambda state: {
            "APPROVE": "apply_changes",
            "APPROVE_WITH_CONDITIONS": "apply_changes",
            "REQUEST_CHANGES": "coding_agent",
            "REJECT": "safe_stop",
        }.get(state.get("last_approval_action"), "safe_stop"),
    )
    builder.add_conditional_edges(
        "apply_changes",
        lambda state: "safe_stop" if state.get("last_error") else "parallel_start",
    )
    builder.add_edge("parallel_start", "validation_agent")
    builder.add_edge("parallel_start", "documentation_draft")
    builder.add_edge("validation_agent", "validation_join")
    builder.add_edge("documentation_draft", "validation_join")
    builder.add_edge("validation_join", "failure_classifier")
    builder.add_conditional_edges("failure_classifier", route_quality)
    builder.add_conditional_edges("retry_router", route_retry)
    builder.add_conditional_edges("replan", route_replan)
    builder.add_edge("documentation_release_agent", "prepare_release_approval")
    builder.add_edge("prepare_release_approval", "release_approval_gate")
    builder.add_conditional_edges("release_approval_gate", route_release_approval)
    for terminal in (
        "finalize_ready",
        "finalize_ready_with_conditions",
        "finalize_not_ready",
        "rollback",
        "safe_stop",
    ):
        builder.add_edge(terminal, END)
    return builder.compile(checkpointer=checkpointer)
