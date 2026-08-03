import pytest
from pydantic import ValidationError

from app.scenarios.url_shortener.profile import URL_SHORTENER_PROFILE


def test_url_shortener_profile_contains_constraints_not_source_code() -> None:
    payload = URL_SHORTENER_PROFILE.model_dump(mode="json")
    assert payload["profile_id"] == "URL_SHORTENER_GREENFIELD"
    assert payload["required_capabilities"] == []
    assert "scope comes only from the user requirement" in payload["summary"]
    serialized = str(payload)
    assert "analytics" not in serialized
    assert "expiration" not in serialized
    assert "aliases" not in serialized
    assert "def create_short_url" not in serialized
    assert "CREATE TABLE" not in serialized


def test_profile_is_frozen() -> None:
    with pytest.raises(ValidationError):
        URL_SHORTENER_PROFILE.profile_id = "GENERIC"  # type: ignore[misc]
