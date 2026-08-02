from dataclasses import dataclass

from app.config import Settings
from app.schemas.agents.common import FailureCategory


@dataclass(frozen=True)
class RetryDecision:
    allowed: bool
    next_count: int
    reason: str


class RetryPolicy:
    """Bound retries by stage and permanently block security/policy retry loops."""

    def __init__(self, settings: Settings) -> None:
        self.limits = {
            "requirement": settings.REQUIREMENT_AGENT_MAX_RETRIES,
            "design": settings.DESIGN_AGENT_MAX_RETRIES,
            "planning": settings.PLANNING_AGENT_MAX_RETRIES,
            "coding": settings.CODING_AGENT_MAX_RETRIES,
            "validation": settings.VALIDATION_AGENT_MAX_RETRIES,
        }

    def decide(
        self,
        stage: str,
        current_count: int,
        category: FailureCategory | str | None,
    ) -> RetryDecision:
        category_value = category.value if isinstance(category, FailureCategory) else category
        if category_value in {"POLICY_VIOLATION", "CRITICAL_SECURITY_FAILURE"}:
            return RetryDecision(False, current_count, "Security failures are never retried.")
        next_count = current_count + 1
        allowed = next_count <= self.limits.get(stage, 0)
        reason = "Retry permitted." if allowed else "Retry limit exhausted."
        return RetryDecision(allowed, next_count, reason)
