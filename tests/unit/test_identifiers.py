import re
from datetime import UTC

import pytest

from app.core.identifiers import (
    new_approval_id,
    new_correlation_id,
    new_short_url_id,
    new_thread_id,
    new_workflow_id,
)
from app.core.time import utc_now


@pytest.mark.parametrize(
    ("factory", "prefix"),
    [
        (new_workflow_id, "WF"),
        (new_thread_id, "TH"),
        (new_approval_id, "APR"),
        (new_short_url_id, "URL"),
        (new_correlation_id, "COR"),
    ],
)
def test_identifier_format_and_uniqueness(factory, prefix: str) -> None:
    identifiers = {factory() for _ in range(250)}

    assert len(identifiers) == 250
    assert all(re.fullmatch(rf"{prefix}-[0-9A-F]{{12}}", value) for value in identifiers)


def test_utc_now_is_timezone_aware_utc() -> None:
    value = utc_now()

    assert value.tzinfo is UTC
    assert value.utcoffset().total_seconds() == 0
