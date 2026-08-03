from app.agents.runner import AgentRunner
from app.schemas.agents.design import DesignOutput


class DesignAgent:
    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    def run(self, state: dict) -> dict:
        retry = state.get("retry_counts", {}).get("design", 0)
        return self.runner.run(
            workflow_id=state["workflow_id"],
            agent_name="DESIGN_AGENT",
            stage="DESIGN",
            prompt_name="design-agent.md",
            input_payload={
                "workflow_id": state["workflow_id"],
                "scenario_type": state["scenario_type"],
                "scripted_scenario": state["scripted_scenario"],
                "scenario_profile": state.get("scenario_profile", {}),
                "retry_number": retry,
                "approved_requirement": state["approved_requirement"],
                "repository_analysis": state.get("repository_analysis", {}),
                "repository_scan": state.get("repository_scan", {}),
            },
            output_model=DesignOutput,
            markdown_name="04-architecture-design.md",
            attempt=retry + 1,
        )
