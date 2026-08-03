from app.agents.runner import AgentRunner
from app.orchestration.planning_policy import (
    normalize_scenario_path_policy,
    planning_governance_context,
    planning_scenario_context,
)
from app.schemas.agents.planning import PlanningOutput


class PlanningAgent:
    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    def run(self, state: dict) -> dict:
        scenario_profile = state.get("scenario_profile", {})
        retry_number = state.get("retry_counts", {}).get("planning", 0)
        previous_plan = state.get("implementation_plan", {})
        governance = planning_governance_context()
        return self.runner.run(
            workflow_id=state["workflow_id"],
            agent_name="PLANNING_AGENT",
            stage="PLANNING",
            prompt_name=(
                "planning-correction-agent.md" if retry_number else "planning-agent.md"
            ),
            input_payload={
                "workflow_id": state["workflow_id"],
                "scenario_type": state["scenario_type"],
                "scripted_scenario": state["scripted_scenario"],
                "scenario_profile": planning_scenario_context(scenario_profile),
                "scenario_path_policy": normalize_scenario_path_policy(scenario_profile),
                "retry_number": retry_number,
                "approved_requirement": state["approved_requirement"],
                "architecture_design": state["architecture_design"],
                "repository_analysis": state.get("repository_analysis", {}),
                "repository_scan": state.get("repository_scan", {}),
                **governance,
                "generated_task_ids": [
                    task.get("task_id") for task in previous_plan.get("tasks", [])
                ],
                "execution_order": list(previous_plan.get("execution_order", [])),
                "validation_errors": list(state.get("planning_validation_errors", [])),
                "previous_plan": previous_plan if retry_number else {},
            },
            output_model=PlanningOutput,
            markdown_name="05-implementation-plan.md",
            attempt=retry_number + 1,
        )
