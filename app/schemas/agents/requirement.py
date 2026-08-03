from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.agents.common import AgentInput, RiskLevel


class RequirementStatus(StrEnum):
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    REJECTED_AS_UNSAFE = "REJECTED_AS_UNSAFE"


class ClarificationQuestion(BaseModel):
    question_id: str = Field(pattern=r"^Q-(?:[0-9]{3}|[A-Z]+-[0-9]{3})$")
    question: str = Field(min_length=1, max_length=500)


class RequirementAgentInput(AgentInput):
    original_requirement: str = Field(min_length=1, max_length=10000)
    clarification_answers: list[dict[str, str]] = Field(default_factory=list)


class RequirementOutput(BaseModel):
    normalized_requirement: str
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    assumptions: list[str]
    ambiguities: list[str]
    clarification_questions: list[ClarificationQuestion]
    acceptance_criteria: list[str]
    risks: list[str]
    material_ambiguity: bool
    risk_level: RiskLevel
    status: RequirementStatus
