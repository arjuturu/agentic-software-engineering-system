from pathlib import Path

SCENARIO_PROMPT_NAMES = (
    "scenarios/url-shortener-context.md",
    "scenarios/url-shortener-validation.md",
)


def scenario_prompt_names(profile_id: str, agent_name: str) -> tuple[str, ...]:
    if profile_id != "URL_SHORTENER_GREENFIELD":
        return ()
    prompts = [SCENARIO_PROMPT_NAMES[0]]
    if agent_name == "VALIDATION_AGENT":
        prompts.append(SCENARIO_PROMPT_NAMES[1])
    return tuple(prompts)


def prompt_path(prompt_root: Path, relative_name: str) -> Path:
    """Resolve one allow-listed scenario prompt beneath the prompt root."""
    if relative_name not in SCENARIO_PROMPT_NAMES:
        raise ValueError("Unknown scenario prompt")
    root = prompt_root.resolve()
    path = (root / relative_name).resolve()
    path.relative_to(root)
    return path
