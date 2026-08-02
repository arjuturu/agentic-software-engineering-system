from app.artifacts.renderer import render_artifact


def test_renderer_redacts_secrets_and_absolute_paths() -> None:
    rendered = render_artifact(
        "09-test-report.md",
        "WF-TEST",
        1,
        {"api_key": "secret-value", "path": "C:\\private\\project\\file.py"},
    )
    assert "secret-value" not in rendered
    assert "C:\\private" not in rendered
    assert "[REDACTED]" in rendered
