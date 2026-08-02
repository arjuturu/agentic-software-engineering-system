from app.agents.runner import AgentRunner
from app.schemas.agents.planning import PlanningOutput


class PlanningAgent:
    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    def run(self, state: dict) -> dict:
        return self.runner.run(
            workflow_id=state["workflow_id"],
            agent_name="PLANNING_AGENT",
            stage="PLANNING",
            prompt_name="planning-agent.md",
            input_payload={
                "workflow_id": state["workflow_id"],
                "scenario_type": state["scenario_type"],
                "scripted_scenario": state["scripted_scenario"],
                "scenario_profile": state.get("scenario_profile", {}),
                "retry_number": state.get("retry_counts", {}).get("planning", 0),
                "approved_requirement": state["approved_requirement"],
                "architecture_design": state["architecture_design"],
            },
            output_model=PlanningOutput,
            markdown_name="05-implementation-plan.md",
        )
