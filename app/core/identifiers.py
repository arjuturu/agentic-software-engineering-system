from uuid import uuid4


def _identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12].upper()}"


def new_workflow_id() -> str:
    return _identifier("WF")


def new_thread_id() -> str:
    return _identifier("TH")


def new_approval_id() -> str:
    return _identifier("APR")


def new_short_url_id() -> str:
    return _identifier("URL")


def new_correlation_id() -> str:
    return _identifier("COR")
