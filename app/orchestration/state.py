from typing import Any, TypedDict


class EngineeringWorkflowState(TypedDict, total=False):
    workflow_id: str
    thread_id: str
    correlation_id: str
    scenario_type: str
    scenario_profile: dict[str, Any]
    scenario_path_policy: dict[str, Any]
    execution_mode: str
    scripted_scenario: str
    workspace_name: str
    source_workspace: str
    repository_path: str
    original_requirement: str
    requirement_analysis: dict[str, Any]
    clarification_answers: list[dict[str, str]]
    approved_requirement: dict[str, Any]
    requirement_version: int
    architecture_design: dict[str, Any]
    architecture_version: int
    implementation_plan: dict[str, Any]
    planning_validation_errors: list[dict[str, Any]]
    planning_correction_context: dict[str, Any]
    active_task: dict[str, Any]
    task_validation_result: dict[str, Any]
    all_required_tasks_completed: bool
    retry_context: dict[str, Any]
    repository_context: list[dict[str, Any]]
    satisfied_task_ids: list[str]
    edit_policy_contexts: list[dict[str, Any]]
    plan_version: int
    repository_scan: dict[str, Any]
    repository_analysis: dict[str, Any]
    code_change_plan: dict[str, Any]
    coding_attempt: dict[str, Any]
    implementation_result: dict[str, Any]
    baseline_commit: str
    working_branch: str
    current_commit: str
    changed_files: list[str]
    git_diff_artifact: str
    validation_result: dict[str, Any]
    target_contract_evidence: dict[str, Any]
    documentation_draft: dict[str, Any]
    release_package: dict[str, Any]
    pending_interaction: dict[str, Any]
    pending_approval: dict[str, Any]
    approval_history: list[dict[str, Any]]
    last_approval_action: str
    retry_counts: dict[str, int]
    failure_history: list[dict[str, Any]]
    replanning_history: list[dict[str, Any]]
    rollback_history: list[dict[str, Any]]
    last_error: dict[str, Any]
    artifact_references: dict[str, str]
    stale_outputs: list[str]
    replan_level: str
    current_stage: str
    workflow_status: str
    state_version: int
    final_release_status: str
    validation_branch_complete: bool
    documentation_branch_complete: bool
    parallel_join_complete: bool
    started_at: str
    updated_at: str
    completed_at: str
