from app.scenarios.url_shortener.contract import (
    REQUIRED_ROUTE_METHODS,
    URLShortenerContract,
    required_route_methods_from_requirement,
    validate_openapi_routes,
)


def _openapi() -> dict:
    return {
        "paths": {
            path: {method: {} for method in methods}
            for path, methods in REQUIRED_ROUTE_METHODS.items()
        }
    }


def test_complete_openapi_contract_passes() -> None:
    check = validate_openapi_routes(_openapi())
    report = URLShortenerContract.from_checks([check])
    assert check.passed
    assert report.status == "PASS"


def test_missing_or_wrong_method_fails_with_evidence() -> None:
    document = _openapi()
    document["paths"]["/api/v1/urls"] = {"get": {}}
    check = validate_openapi_routes(document)
    assert not check.passed
    assert "POST /api/v1/urls" in check.evidence["missing"]


def test_route_contract_uses_only_explicit_requirement_routes() -> None:
    requirement = (
        "Implement POST /api/v1/urls and GET /{short_code}. "
        "Analytics, expiration, custom aliases, and health endpoints are out of scope."
    )

    routes = required_route_methods_from_requirement(requirement)

    assert routes == {
        "/api/v1/urls": frozenset({"post"}),
        "/{short_code}": frozenset({"get"}),
    }
    assert validate_openapi_routes(
        {
            "paths": {
                "/api/v1/urls": {"post": {}},
                "/{short_code}": {"get": {}},
            }
        },
        routes,
    ).passed
