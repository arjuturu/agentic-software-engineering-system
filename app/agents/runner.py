import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from app.agents.base import PromptLoader
from app.agents.provider import StructuredModelProvider
from app.repositories.agent_execution_repository import AgentExecutionRepository
from app.repositories.audit_repository import AuditRepository
from app.scenarios.url_shortener.context import scenario_prompt_names
from app.services.artifact_service import ArtifactService

logger = logging.getLogger(__name__)


class AgentRunner:
    def __init__(
        self,
        provider: StructuredModelProvider,
        prompt_loader: PromptLoader,
        sessions: sessionmaker[Session],
        artifacts: ArtifactService,
    ) -> None:
        self.provider = provider
        self.prompt_loader = prompt_loader
        self.sessions = sessions
        self.artifacts = artifacts

    def _system_prompt(self, prompt_name: str, profile: dict, agent_name: str) -> str:
        prompts = [self.prompt_loader.load(prompt_name)]
        for scenario_prompt in scenario_prompt_names(profile.get("profile_id", ""), agent_name):
            prompts.append(self.prompt_loader.load(scenario_prompt))
        return "\n\n".join(prompts)

    def run(
        self,
        *,
        workflow_id: str,
        agent_name: str,
        stage: str,
        prompt_name: str,
        input_payload: dict[str, Any],
        output_model: type[BaseModel],
        markdown_name: str,
        attempt: int = 1,
    ) -> dict[str, Any]:
        with self.sessions.begin() as session:
            execution = AgentExecutionRepository(session).start(
                workflow_id, agent_name, stage, attempt
            )
            execution_id = execution.id
            AuditRepository(session).add(
                workflow_id, "AGENT_STARTED", stage, {"agent": agent_name, "attempt": attempt}
            )
        try:
            output = self.provider.generate(
                agent_name=agent_name,
                system_prompt=self._system_prompt(
                    prompt_name,
                    input_payload.get("scenario_profile", {}),
                    agent_name,
                ),
                input_payload=input_payload,
                output_model=output_model,
            )
            payload = output_model.model_validate(output).model_dump(mode="json")
            json_name = f"{Path(markdown_name).stem}.json"
            json_ref = self.artifacts.write_json(
                workflow_id, f"{agent_name}_JSON", json_name, payload
            )
            markdown_ref = self.artifacts.write_markdown(
                workflow_id, f"{agent_name}_MARKDOWN", markdown_name, payload, [json_ref]
            )
            with self.sessions.begin() as session:
                item = session.get(
                    __import__("app.database.models", fromlist=["AgentExecution"]).AgentExecution,
                    execution_id,
                )
                AgentExecutionRepository(session).finish(item, markdown_ref)
                AuditRepository(session).add(
                    workflow_id,
                    "AGENT_COMPLETED",
                    stage,
                    {"agent": agent_name, "artifact": markdown_ref},
                )
            return payload
        except Exception as exc:
            diagnostics = dict(getattr(exc, "details", {}) or {})
            diagnostics.setdefault("agent_name", agent_name)
            diagnostics.setdefault("exception_class", type(exc).__name__)
            diagnostics.setdefault("field_paths", [])
            diagnostics.setdefault("validation_error_types", [])
            diagnostics.setdefault("finish_reason", None)
            diagnostics.setdefault("input_tokens", None)
            diagnostics.setdefault("output_tokens", None)
            diagnostics.setdefault("http_request_made", False)
            error_code = getattr(exc, "error_code", "AGENT_FAILED")
            logger.warning(
                "agent=%s status=FAILED error_type=%s request_made=%s",
                agent_name,
                diagnostics["exception_class"],
                diagnostics["http_request_made"],
            )
            with self.sessions.begin() as session:
                item = session.get(
                    __import__("app.database.models", fromlist=["AgentExecution"]).AgentExecution,
                    execution_id,
                )
                AgentExecutionRepository(session).fail(
                    item, json.dumps(diagnostics, sort_keys=True)
                )
                AuditRepository(session).add(
                    workflow_id,
                    "AGENT_FAILED",
                    stage,
                    {
                        "agent": agent_name,
                        "error_code": error_code,
                        "diagnostics": diagnostics,
                    },
                )
            raise
