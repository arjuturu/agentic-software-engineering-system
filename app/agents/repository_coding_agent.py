from app.agents.runner import AgentRunner
from app.schemas.agents.coding import CodingOutput, RepositoryAnalysisOutput


class RepositoryCodingAgent:
    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    def analyze(self, state: dict, scan: dict) -> dict:
        return self.runner.run(
            workflow_id=state["workflow_id"],
            agent_name="REPOSITORY_AGENT",
            stage="REPOSITORY_ANALYSIS",
            prompt_name="repository-analysis-agent.md",
            input_payload={
                "workflow_id": state["workflow_id"],
                "scenario_type": state["scenario_type"],
                "scripted_scenario": state["scripted_scenario"],
                "retry_number": 0,
                "deterministic_scan": scan,
            },
            output_model=RepositoryAnalysisOutput,
            markdown_name="06-repository-impact-analysis.md",
        )

    def code(self, state: dict, file_hashes: dict[str, str]) -> dict:
        retry = state.get("retry_counts", {}).get("coding", 0)
        return self.runner.run(
            workflow_id=state["workflow_id"],
            agent_name="CODING_AGENT",
            stage="CODING",
            prompt_name="coding-fix-agent.md" if retry else "coding-agent.md",
            input_payload={
                "workflow_id": state["workflow_id"],
                "scenario_type": state["scenario_type"],
                "scripted_scenario": state["scripted_scenario"],
                "retry_number": retry,
                "implementation_plan": state["implementation_plan"],
                "repository_analysis": state["repository_analysis"],
                "validation_failure": state.get("validation_result"),
                "file_hashes": file_hashes,
            },
            output_model=CodingOutput,
            markdown_name="07-code-change-plan.md",
            attempt=retry + 1,
        )
