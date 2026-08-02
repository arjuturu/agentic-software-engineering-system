from app.config import Settings
from app.orchestration.retries import RetryPolicy


def test_retry_is_bounded_and_security_is_never_retried() -> None:
    policy = RetryPolicy(Settings(_env_file=None, CODING_AGENT_MAX_RETRIES=1))
    assert policy.decide("coding", 0, "IMPLEMENTATION_DEFECT").allowed
    assert not policy.decide("coding", 1, "IMPLEMENTATION_DEFECT").allowed
    assert not policy.decide("coding", 0, "POLICY_VIOLATION").allowed
