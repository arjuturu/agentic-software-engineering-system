import re
from pathlib import Path

SCRIPT_PATH = Path("scripts/run_phase4_scripted_demo.ps1")


def _script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_runner_declares_modes_scenarios_and_real_scripted_ids() -> None:
    script = _script()

    assert '[ValidateSet("Automatic", "Interactive")]' in script
    assert '[ValidateSet("Greenfield", "Brownfield", "Ambiguous", "All")]' in script
    assert "URL_SHORTENER_GREENFIELD_HAPPY_PATH" in script
    assert "URL_SHORTENER_BROWNFIELD_ANALYTICS" in script
    assert "URL_SHORTENER_AMBIGUOUS_ALIASES" in script
    assert "OFFLINE SCRIPTED PLATFORM TEST DOUBLE" not in script
    assert "Expected provider mode: SCRIPTED" in script


def test_runner_uses_greenfield_as_both_independent_source_branches() -> None:
    script = _script()

    assert "$greenSource = $green.workspacePath" in script
    assert script.count("-SourceWorkspaceName $greenSource") == 2
    assert "$WorkspacePrefix-brownfield-$timestamp" in script
    assert "$WorkspacePrefix-ambiguous-$timestamp" in script
    assert "Brownfield and Ambiguous must use separate destination workspaces." in script


def test_runner_has_all_alias_defaults_and_real_interrupt_metadata() -> None:
    script = _script()

    for number in range(1, 7):
        assert f'"Q-ALIAS-{number:03d}"' in script
    assert "$pending.clarificationId" in script
    assert "$pending.stateVersion" in script
    assert "questionId = $questionId" in script
    assert "$pending.approvalId" in script
    assert "$pending.gateType" in script
    assert "$pending.allowedActions" in script
    assert "stateVersion = $pending.stateVersion" in script


def test_runner_polls_terminal_state_with_a_bound_and_nonzero_failure_exit() -> None:
    script = _script()

    assert "[int]$MaxPollAttempts = 600" in script
    assert "[int]$PollIntervalMilliseconds = 500" in script
    assert "for ($attempt = 1; $attempt -le $MaxPollAttempts; $attempt++)" in script
    for terminal in (
        "READY",
        "NOT_READY",
        "FAILED",
        "CANCELLED",
        "ROLLBACK_COMPLETE",
    ):
        assert f'"{terminal}"' in script
    assert "$exitCode = 1" in script
    assert "exit $exitCode" in script


def test_runner_only_drives_public_rest_contract_and_owned_server() -> None:
    script = _script()
    lowered = script.casefold()

    for endpoint in (
        "/api/v1/workflows",
        "/clarifications",
        "/approvals/",
        "/artifacts",
        "/audit",
        "/health/live",
        "/health/ready",
    ):
        assert endpoint in script
    assert "Start-Process" in script
    assert "if ($null -ne $server -and -not $server.HasExited)" in script
    assert "Stop-Process -Id $server.Id" in script
    prohibited = (
        r"\bupdate\s+workflow_",
        r"\binsert\s+into\s+workflow_",
        r"\bdelete\s+from\s+workflow_",
        r"\bgraph\.invoke\b",
        r"\bbase\.metadata\b",
        r"\bsqlite3(?:\.exe)?\b",
        r"\bset-content\b",
        r"\badd-content\b",
        r"\bout-file\b",
    )
    assert not any(re.search(pattern, lowered) for pattern in prohibited)
