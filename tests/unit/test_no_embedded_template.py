from pathlib import Path

from app.agents.scripted_provider import ScriptedProvider
from app.scenarios.url_shortener.profile import URL_SHORTENER_PROFILE


def test_scripted_provider_has_no_embedded_url_shortener_implementation() -> None:
    source = Path(ScriptedProvider.__module__.replace(".", "/") + ".py")
    text = source.read_text(encoding="utf-8")
    assert "/api/v1/urls" not in text
    assert "URLShortener" not in text
    assert "short_urls" not in text


def test_profile_does_not_embed_target_source_bodies() -> None:
    text = URL_SHORTENER_PROFILE.model_dump_json()
    assert "from fastapi import" not in text
    assert "mapped_column(" not in text
