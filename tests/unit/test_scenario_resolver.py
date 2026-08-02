import pytest

from app.scenarios.resolver import resolve_scenario_profile


def test_resolves_url_shortener_only_with_strong_greenfield_evidence() -> None:
    profile = resolve_scenario_profile(
        "GREENFIELD",
        "Build a URL shortening service with custom aliases, redirects, and analytics.",
    )
    assert profile["profile_id"] == "URL_SHORTENER_GREENFIELD"
    assert profile["required_capabilities"] == []


@pytest.mark.parametrize(
    ("scenario", "requirement"),
    [
        ("GREENFIELD", "Validate this URL."),
        ("BROWNFIELD", "Add URL shortening redirects and analytics."),
        ("GREENFIELD", "Build an analytics dashboard."),
    ],
)
def test_weak_or_incompatible_evidence_stays_generic(scenario: str, requirement: str) -> None:
    assert resolve_scenario_profile(scenario, requirement)["profile_id"] == "GENERIC"


def test_resolver_is_deterministic() -> None:
    requirement = "Create a short URL service with expiration support."
    assert resolve_scenario_profile("GREENFIELD", requirement) == resolve_scenario_profile(
        "GREENFIELD", requirement
    )
