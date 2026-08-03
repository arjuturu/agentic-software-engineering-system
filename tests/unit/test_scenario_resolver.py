import pytest

from app.scenarios.resolver import resolve_scenario_profile


def test_resolves_url_shortener_only_with_strong_greenfield_evidence() -> None:
    profile = resolve_scenario_profile(
        "GREENFIELD",
        "Build a URL shortening service with custom aliases, redirects, and analytics.",
    )
    assert profile["profile_id"] == "URL_SHORTENER_GREENFIELD"
    assert profile["required_capabilities"] == []


def test_resolves_required_demo_wording_with_plural_short_codes() -> None:
    profile = resolve_scenario_profile(
        "GREENFIELD",
        (
            "Build a local URL-shortening API. Generate secure eight-character "
            "alphanumeric short codes using Python secrets."
        ),
    )

    assert profile["profile_id"] == "URL_SHORTENER_GREENFIELD"


@pytest.mark.parametrize(
    ("scenario", "requirement"),
    [
        ("GREENFIELD", "Validate this URL."),
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


def test_brownfield_uses_repository_aware_url_shortener_profile() -> None:
    profile = resolve_scenario_profile(
        "BROWNFIELD", "Enhance an existing URL shortener with click analytics."
    )

    assert profile["profile_id"] == "URL_SHORTENER_BROWNFIELD"
    assert profile["required_capabilities"] == []


def test_ambiguous_aliases_use_source_based_url_shortener_profile() -> None:
    profile = resolve_scenario_profile(
        "AMBIGUOUS", "Add support for optional custom aliases."
    )

    assert profile["profile_id"] == "URL_SHORTENER_AMBIGUOUS_ALIASES"
    assert profile["scenario_type"] == "AMBIGUOUS"
    assert profile["required_capabilities"] == []
