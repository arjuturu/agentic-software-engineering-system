from pathlib import Path

from app.core.exceptions import ApplicationError

_ALLOWED_PROMPTS = {
    "requirement-agent.md",
    "design-agent.md",
    "planning-agent.md",
    "repository-analysis-agent.md",
    "coding-agent.md",
    "coding-fix-agent.md",
    "validation-agent.md",
    "failure-classification-agent.md",
    "documentation-release-agent.md",
}


class PromptLoader:
    """Load only approved UTF-8 Markdown prompts from the control-plane prompt root."""

    def __init__(self, prompt_root: Path) -> None:
        self.prompt_root = prompt_root.resolve()
        self._cache: dict[str, str] = {}

    def load(self, file_name: str) -> str:
        if (
            not file_name
            or Path(file_name).is_absolute()
            or Path(file_name).name != file_name
            or file_name not in _ALLOWED_PROMPTS
            or Path(file_name).suffix.lower() != ".md"
        ):
            raise ApplicationError("Prompt access was blocked.", "PROMPT_PATH_BLOCKED", 400)
        path = (self.prompt_root / file_name).resolve()
        try:
            path.relative_to(self.prompt_root)
        except ValueError as exc:
            raise ApplicationError(
                "Prompt access was blocked.", "PROMPT_PATH_BLOCKED", 400
            ) from exc
        if not path.is_file():
            raise ApplicationError("The configured prompt is missing.", "PROMPT_NOT_FOUND", 500)
        if file_name not in self._cache:
            self._cache[file_name] = path.read_text(encoding="utf-8")
        return self._cache[file_name]
