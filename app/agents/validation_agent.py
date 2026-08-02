from app.agents.runner import AgentRunner
from app.schemas.agents.validation import ValidationOutput


class ValidationAgent:
    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    def run(self, state: dict, command_results: list[dict]) -> dict:
        retry = state.get("retry_counts", {}).get("coding", 0)
        return self.runner.run(
            workflow_id=state["workflow_id"],
            agent_name="VALIDATION_AGENT",
            stage="VALIDATION",
            prompt_name="validation-agent.md",
            input_payload={
                "workflow_id": state["workflow_id"],
                "scenario_type": state["scenario_type"],
                "scripted_scenario": state["scripted_scenario"],
                "scenario_profile": state.get("scenario_profile", {}),
                "retry_number": retry,
                "command_results": command_results,
                "implementation_result": state["implementation_result"],
                "approved_requirement": state.get("approved_requirement", {}),
                "architecture_design": state.get("architecture_design", {}),
                "implementation_plan": state.get("implementation_plan", {}),
                "target_contract_evidence": state.get("target_contract_evidence", {}),
            },
            output_model=ValidationOutput,
            markdown_name="09-test-report.md",
            attempt=retry + 1,
        )
