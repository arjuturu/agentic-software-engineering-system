from datetime import datetime

from pydantic import BaseModel


class ReliabilityFilters(BaseModel):
    scenario_type: str | None = None
    scenario_profile: str | None = None
    workflow_id: str | None = None
    provider: str | None = None


class ReliabilitySummary(BaseModel):
    total_workflows: int
    ready_workflows: int
    not_ready_workflows: int
    failed_workflows: int
    cancelled_workflows: int
    rollback_complete_workflows: int
    success_rate_percent: float


class DurationMetrics(BaseModel):
    average_duration_seconds: float | None
    minimum_duration_seconds: float | None
    maximum_duration_seconds: float | None
    average_time_to_ready_seconds: float | None
    average_time_to_failure_seconds: float | None
    failure_to_resolution_seconds: float | None = None


class InteractionMetrics(BaseModel):
    clarification_workflow_count: int
    clarification_event_count: int
    approval_event_count: int
    requirement_approval_count: int
    architecture_plan_approval_count: int
    high_risk_approval_count: int
    release_approval_count: int
    average_approval_count_per_workflow: float | None
    average_clarification_count_per_workflow: float | None


class AggregateReliabilityMetrics(BaseModel):
    planning_retry_count: int
    coding_retry_count: int
    total_retry_count: int
    rollback_triggered_count: int
    safe_stop_count: int


class WorkflowReliabilityDetail(BaseModel):
    workflow_id: str
    scenario_type: str
    scenario_profile: str | None
    provider: str | None = None
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    requirement_version: int
    architecture_version: int
    plan_version: int
    planning_retries: int
    coding_retries: int
    clarification_count: int
    approval_count: int
    rollback_status: str
    final_release_status: str | None


class ScriptedBenchmarkScenario(BaseModel):
    scenario: str
    workflow_id: str
    status: str
    initial_clarification_observed: bool
    source_workspace_topology: str
    retry_count: int
    rollback_status: str


class ScriptedBenchmark(BaseModel):
    complete: bool
    scenarios: list[ScriptedBenchmarkScenario]


class ReliabilityReport(BaseModel):
    generated_at: datetime
    filters: ReliabilityFilters
    data_source: str
    summary: ReliabilitySummary
    duration_metrics: DurationMetrics
    interaction_metrics: InteractionMetrics
    reliability_metrics: AggregateReliabilityMetrics
    scripted_benchmark: ScriptedBenchmark
    unsupported_metrics: dict[str, str]
    workflows: list[WorkflowReliabilityDetail]
