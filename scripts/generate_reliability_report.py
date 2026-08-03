import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database.session import SessionLocal  # noqa: E402
from app.schemas.reliability import ReliabilityFilters  # noqa: E402
from app.services.reliability_metrics import (  # noqa: E402
    ReliabilityMetricsService,
    serialize_report,
    write_report_files,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a read-only reliability report from persisted workflow evidence."
    )
    parser.add_argument("--scenario-profile")
    parser.add_argument("--scenario-type")
    parser.add_argument("--workflow-id")
    parser.add_argument(
        "--provider",
        help="Reserved until provider mode is persisted; currently returns a clear error.",
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    filters = ReliabilityFilters(
        scenario_type=args.scenario_type,
        scenario_profile=args.scenario_profile,
        workflow_id=args.workflow_id,
        provider=args.provider,
    )
    try:
        with SessionLocal() as session:
            report = ReliabilityMetricsService(session).build_report(filters)
        write_report_files(
            report,
            output_json=args.output_json,
            output_markdown=args.output_markdown,
        )
    except (OSError, ValueError) as exc:
        print(f"Reliability report failed: {exc}", file=sys.stderr)
        return 1
    if args.output_json:
        print(f"JSON report: {args.output_json.resolve()}")
    if args.output_markdown:
        print(f"Markdown report: {args.output_markdown.resolve()}")
    if not args.output_json and not args.output_markdown:
        print(serialize_report(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
