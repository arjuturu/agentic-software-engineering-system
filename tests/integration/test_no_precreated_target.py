from pathlib import Path


def test_production_target_is_not_precreated_in_control_plane() -> None:
    project_root = Path(__file__).resolve().parents[2]
    assert not (project_root / "workspace" / "url-shortener-greenfield").exists()
    assert not (project_root / "app" / "url_shortener_target").exists()
