from pathlib import Path

from app.scenarios.url_shortener.validators import URLShortenerValidator


def test_control_plane_import_is_reported_from_synthetic_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "main.py").write_text(
        "from app.orchestration.graph import build_workflow_graph\n", encoding="utf-8"
    )
    assert URLShortenerValidator._control_plane_imports(target) == ["main.py"]


def test_independent_target_source_is_accepted(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "main.py").write_text(
        "from fastapi import FastAPI\nfrom app.services.url_service import URLService\n",
        encoding="utf-8",
    )
    assert URLShortenerValidator._control_plane_imports(target) == []
