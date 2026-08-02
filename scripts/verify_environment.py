import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import get_settings  # noqa: E402


def report(name: str, passed: bool, detail: str) -> bool:
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
    return passed


def main() -> int:
    settings = get_settings()
    checks: list[bool] = []

    checks.append(
        report(
            "Python",
            sys.version_info >= (3, 11),
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )

    for directory in (ROOT / "data", settings.WORKSPACE_ROOT, settings.ARTIFACT_ROOT):
        checks.append(report("Directory", directory.is_dir(), str(directory)))

    try:
        database_name = make_url(settings.DATABASE_URL).database
        if not database_name:
            raise ValueError("SQLite database path is missing")
        with sqlite3.connect(Path(database_name)) as connection:
            connection.execute("SELECT 1").fetchone()
        checks.append(report("SQLite", True, "connection successful"))
    except Exception as exc:
        checks.append(report("SQLite", False, str(exc)))

    git = shutil.which("git")
    if git:
        try:
            result = subprocess.run(
                [git, "--version"],
                check=False,
                capture_output=True,
                text=True,
                shell=False,
                timeout=settings.MAX_COMMAND_SECONDS,
            )
            checks.append(report("Git", result.returncode == 0, result.stdout.strip()))
        except (OSError, subprocess.SubprocessError) as exc:
            checks.append(report("Git", False, str(exc)))
    else:
        checks.append(report("Git", False, "executable not found"))

    try:
        script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        heads = script.get_heads()
        checks.append(report("Alembic", bool(heads), f"migration head: {', '.join(heads)}"))
    except Exception as exc:
        checks.append(report("Alembic", False, str(exc)))

    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())

