from app.scenarios.url_shortener.contract import (
    REQUIRED_ROUTE_METHODS,
    URLShortenerContract,
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
