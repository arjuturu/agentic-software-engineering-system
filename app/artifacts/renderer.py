import json
import re
from pathlib import PurePath
from typing import Any

from app.artifacts.templates import ARTIFACT_TITLES

_SENSITIVE_KEYS = ("api_key", "token", "password", "secret", "credential")
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def _sanitize(value: Any, key: str = "") -> Any:
    if any(marker in key.lower() for marker in _SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): _sanitize(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        if value.startswith("/") or value.startswith("\\\\") or _WINDOWS_ABSOLUTE.match(value):
            return PurePath(value).name or "[PATH REDACTED]"
        return value
    return value


def render_artifact(
    file_name: str,
    workflow_id: str,
    version: int,
    content: dict[str, Any],
    evidence_references: list[str] | None = None,
) -> str:
    """Render stable, redacted Markdown from JSON-compatible structured content."""
    title = ARTIFACT_TITLES.get(file_name, "Workflow Artifact")
    safe_content = _sanitize(content)
    lines = [
        f"# {title}",
        "",
        f"- Workflow ID: {workflow_id}",
        f"- Version: {version}",
        "",
        "## Structured Evidence",
        "",
        "~~~json",
        json.dumps(safe_content, indent=2, sort_keys=True, ensure_ascii=False),
        "~~~",
    ]
    if evidence_references:
        lines.extend(["", "## Evidence References", ""])
        lines.extend(f"- {reference}" for reference in evidence_references)
    return "\n".join(lines) + "\n"
