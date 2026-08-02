from app.agents.runner import AgentRunner
from app.schemas.agents.release import ReleaseOutput


class DocumentationReleaseAgent:
    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    @staticmethod
    def draft(state: dict) -> dict:
        return {
            "status": "DRAFT",
            "implementation_summary": state["implementation_result"].get(
                "implementation_summary", ""
            ),
            "tests_verified": False,
        }

    def release(self, state: dict) -> dict:
        return self.runner.run(
            workflow_id=state["workflow_id"],
            agent_name="DOCUMENTATION_RELEASE_AGENT",
            stage="RELEASE",
            prompt_name="documentation-release-agent.md",
            input_payload={
                "workflow_id": state["workflow_id"],
                "scenario_type": state["scenario_type"],
                "scripted_scenario": state["scripted_scenario"],
                "scenario_profile": state.get("scenario_profile", {}),
                "retry_number": 0,
                "validation_result": state["validation_result"],
                "documentation_draft": state["documentation_draft"],
                "context": {
                    "changed_files": state.get("changed_files", []),
                    "artifacts": list(state.get("artifact_references", {}).values()),
                },
            },
            output_model=ReleaseOutput,
            markdown_name="12-production-readiness-report.md",
        )
