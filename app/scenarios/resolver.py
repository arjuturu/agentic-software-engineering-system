import re
from enum import StrEnum

from app.scenarios.url_shortener.profile import URL_SHORTENER_PROFILE


class ScenarioProfileId(StrEnum):
    GENERIC = "GENERIC"
    URL_SHORTENER_GREENFIELD = "URL_SHORTENER_GREENFIELD"


_URL_SHORTENER = re.compile(r"\b(url short(?:en(?:er|ing)?)?|short url|short link)\b", re.I)
_SUPPORTING_EVIDENCE = (
    re.compile(r"\bredirect\w*\b", re.I),
    re.compile(r"\bshort[ _-]?code\b", re.I),
    re.compile(r"\balias\w*\b", re.I),
    re.compile(r"\bexpir(?:e|es|ation|y)\w*\b", re.I),
    re.compile(r"\banalytics?\b", re.I),
)


def resolve_scenario_profile(scenario_type: str, requirement: str) -> dict:
    """Return an immutable-by-convention JSON profile from strong scenario evidence."""
    normalized_type = scenario_type.strip().upper()
    strong_match = bool(_URL_SHORTENER.search(requirement))
    supporting_matches = sum(bool(pattern.search(requirement)) for pattern in _SUPPORTING_EVIDENCE)
    if normalized_type == "GREENFIELD" and strong_match and supporting_matches >= 1:
        return URL_SHORTENER_PROFILE.model_dump(mode="json")
    return {
        "profile_id": ScenarioProfileId.GENERIC.value,
        "scenario_type": normalized_type,
        "summary": "Generic governed engineering workflow",
        "required_capabilities": [],
        "allowed_paths": [],
        "validation_rules": [],
    }
