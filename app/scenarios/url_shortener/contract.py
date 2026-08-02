from typing import Any

from pydantic import BaseModel, Field

REQUIRED_ROUTE_METHODS: dict[str, frozenset[str]] = {
    "/": frozenset({"get"}),
    "/health/live": frozenset({"get"}),
    "/health/ready": frozenset({"get"}),
    "/api/v1/urls": frozenset({"post"}),
    "/api/v1/urls/{short_code}": frozenset({"get"}),
    "/api/v1/urls/{short_code}/analytics": frozenset({"get"}),
    "/{short_code}": frozenset({"get"}),
}


class ContractCheck(BaseModel):
    name: str
    passed: bool
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class URLShortenerContract(BaseModel):
    profile_id: str = "URL_SHORTENER_GREENFIELD"
    status: str
    checks: list[ContractCheck]

    @classmethod
    def from_checks(cls, checks: list[ContractCheck]) -> "URLShortenerContract":
        return cls(status="PASS" if all(item.passed for item in checks) else "FAIL", checks=checks)


def validate_openapi_routes(document: dict[str, Any]) -> ContractCheck:
    paths = document.get("paths", {}) if isinstance(document, dict) else {}
    missing = []
    for route, methods in REQUIRED_ROUTE_METHODS.items():
        available = {str(method).lower() for method in paths.get(route, {})}
        for method in sorted(methods - available):
            missing.append(f"{method.upper()} {route}")
    return ContractCheck(
        name="required_routes",
        passed=not missing,
        message=(
            "Required route contract is satisfied."
            if not missing
            else "Required routes are missing."
        ),
        evidence={"missing": missing},
    )
