import re
from typing import Any

from pydantic import BaseModel, Field

REQUIRED_ROUTE_METHODS: dict[str, frozenset[str]] = {
    "/api/v1/urls": frozenset({"post"}),
    "/{short_code}": frozenset({"get"}),
}
_ROUTE_REFERENCE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+(/[A-Za-z0-9_{}./-]*)",
    re.IGNORECASE,
)


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


def required_route_methods_from_requirement(requirement: str) -> dict[str, frozenset[str]]:
    """Extract only HTTP route contracts explicitly stated by the user."""
    routes: dict[str, set[str]] = {}
    for method, path in _ROUTE_REFERENCE.findall(requirement):
        normalized_path = path.rstrip(".,;:")
        routes.setdefault(normalized_path, set()).add(method.casefold())
    return {path: frozenset(methods) for path, methods in routes.items()}


def validate_openapi_routes(
    document: dict[str, Any],
    required_route_methods: dict[str, frozenset[str]] | None = None,
) -> ContractCheck:
    paths = document.get("paths", {}) if isinstance(document, dict) else {}
    missing = []
    contract = REQUIRED_ROUTE_METHODS if required_route_methods is None else required_route_methods
    for route, methods in contract.items():
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
        evidence={"missing": missing, "required_routes": sorted(contract)},
    )
