from app.agents.runner import AgentRunner
from app.schemas.agents.requirement import RequirementOutput


class RequirementAgent:
    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    def run(self, state: dict) -> dict:
        return self.runner.run(
            workflow_id=state["workflow_id"],
            agent_name="REQUIREMENT_AGENT",
            stage="REQUIREMENTS",
            prompt_name="requirement-agent.md",
            input_payload={
                "workflow_id": state["workflow_id"],
                "scenario_type": state["scenario_type"],
                "scripted_scenario": state["scripted_scenario"],
                "retry_number": state.get("retry_counts", {}).get("requirement", 0),
                "original_requirement": state["original_requirement"],
                "clarification_answers": state.get("clarification_answers", []),
            },
            output_model=RequirementOutput,
            markdown_name="01-requirement-analysis.md",
        )
