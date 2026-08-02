import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.config import get_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize local Phase 1 directories.")
    parser.add_argument(
        "--migrate", action="store_true", help="Apply Alembic migrations after setup."
    )
    args = parser.parse_args()

    try:
        settings = get_settings()
        for directory in (
            ROOT / "data",
            settings.WORKSPACE_ROOT,
            settings.ARTIFACT_ROOT,
        ):
            directory.mkdir(parents=True, exist_ok=True)
            print(f"Ready: {directory}")

        if args.migrate:
            command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
            print("Database migrated to head.")

        print("\nNext commands:")
        if not args.migrate:
            print("  alembic upgrade head")
        print("  python scripts/verify_environment.py")
        print("  python -m uvicorn app.main:app --reload")
        return 0
    except Exception as exc:
        print(f"Initialization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

