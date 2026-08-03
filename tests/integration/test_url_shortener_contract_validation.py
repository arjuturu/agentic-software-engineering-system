import json
from pathlib import Path

from app.config import Settings
from app.scenarios.url_shortener.contract import validate_openapi_routes
from app.scenarios.url_shortener.validators import URLShortenerValidator
from app.tools.alembic_runner import AlembicRunner
from app.tools.command_runner import CommandRunner
from app.tools.git_tool import GitTool
from app.tools.models import CommandId, ToolStatus
from app.tools.path_policy import PathPolicy
from app.tools.repository_scanner import RepositoryScanner
from app.tools.test_runner import TestRunner


def test_isolated_target_import_and_openapi_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "synthetic-target"
    (target / "app").mkdir(parents=True)
    (target / "app" / "__init__.py").write_text("", encoding="utf-8")
    routes = [
        '@app.get("/")\ndef root(): return {}',
        '@app.get("/health/live")\ndef live(): return {}',
        '@app.get("/health/ready")\ndef ready(): return {}',
        '@app.post("/api/v1/urls")\ndef create(): return {}',
        '@app.get("/api/v1/urls/{short_code}")\ndef resolve(short_code: str): return {}',
        (
            '@app.get("/api/v1/urls/{short_code}/analytics")\n'
            "def analytics(short_code: str): return {}"
        ),
        '@app.get("/{short_code}")\ndef redirect(short_code: str): return {}',
    ]
    (target / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n\n" + "\n\n".join(routes) + "\n",
        encoding="utf-8",
    )
    settings = Settings(
        _env_file=None,
        WORKSPACE_ROOT=workspace,
        ARTIFACT_ROOT=tmp_path / "artifacts",
        MAX_COMMAND_SECONDS=20,
    )
    policy = PathPolicy(settings, project_root=tmp_path)
    runner = CommandRunner(policy, settings)
    imported = runner.run(CommandId.TARGET_IMPORT_CHECK, target)
    openapi = runner.run(CommandId.TARGET_OPENAPI_CHECK, target)
    assert imported.status == ToolStatus.SUCCESS
    assert openapi.status == ToolStatus.SUCCESS
    assert validate_openapi_routes(json.loads(openapi.stdout)).passed
    validator = URLShortenerValidator(
        policy,
        RepositoryScanner(policy, settings),
        runner,
        TestRunner(runner),
        AlembicRunner(runner),
        GitTool(policy, settings),
    )
    report = validator.validate(target)
    failed_checks = {check.name for check in report.checks if not check.passed}
    assert report.status == "FAIL"
    assert "no_git_remote" in failed_checks
    assert "alembic_configuration" in failed_checks
    assert "migration_cycle" in failed_checks

