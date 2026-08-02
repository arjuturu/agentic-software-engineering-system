param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$UseExistingServer
)

$ErrorActionPreference = "Stop"
if ($env:LLM_MODE -ne "OPENAI") {
    Write-Error "Set LLM_MODE=OPENAI in the process environment before running this demo."
    exit 1
}
if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    Write-Error "OPENAI_API_KEY is not present in the process environment. Its value was not printed."
    exit 1
}
if ([string]::IsNullOrWhiteSpace($env:OPENAI_MODEL)) {
    Write-Error "OPENAI_MODEL is not present in the process environment."
    exit 1
}

$server = $null
try {
    if (-not $UseExistingServer) {
        $server = Start-Process -FilePath "python" -ArgumentList @(
            "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"
        ) -PassThru -WindowStyle Hidden
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            try {
                Invoke-RestMethod -Uri "$BaseUrl/health/live" -TimeoutSec 2 | Out-Null
                break
            } catch {
                Start-Sleep -Milliseconds 500
            }
        }
    }

    Write-Host "REAL SIX-AGENT OPENAI GREENFIELD RUN — human approvals are mandatory"
    $request = @{
        scenarioType = "GREENFIELD"
        requirement = "Build a production-style independent URL shortening FastAPI application with short-code creation, optional custom aliases and expiration, redirect behavior, analytics, health endpoints, SQLite, SQLAlchemy 2.x, Alembic migration cycling, tests, Ruff, safe configuration, and local documentation. Do not import the control-plane project or configure a Git remote."
        workspaceName = "url-shortener-greenfield"
        scriptedScenario = "HAPPY_PATH"
    } | ConvertTo-Json
    $workflow = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/workflows" -ContentType "application/json" -Body $request

    $terminalStatuses = @("READY", "READY_WITH_CONDITIONS", "NOT_READY", "REJECTED", "STOPPED")
    while ($terminalStatuses -notcontains $workflow.status) {
        if ($workflow.pendingInteraction.type -eq "CLARIFICATION") {
            $answers = @()
            foreach ($question in $workflow.pendingInteraction.payload.questions) {
                $answer = Read-Host "$($question.question_id): $($question.question)"
                if ([string]::IsNullOrWhiteSpace($answer)) {
                    throw "Clarification answers cannot be empty."
                }
                $answers += @{ questionId = $question.question_id; answer = $answer }
            }
            $clarification = @{
                type = "CLARIFICATION_RESPONSE"
                stateVersion = $workflow.pendingInteraction.payload.stateVersion
                answers = $answers
            } | ConvertTo-Json -Depth 5
            $workflow = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/workflows/$($workflow.workflowId)/clarifications" -ContentType "application/json" -Body $clarification
            continue
        }
        if (-not $workflow.pendingApproval.approvalId) {
            throw "Workflow paused without a supported human interaction."
        }
        $pending = $workflow.pendingApproval
        Write-Host "Gate: $($pending.gateType); workflow: $($workflow.workflowId); state: $($pending.stateVersion)"
        Write-Host "Allowed actions: $($pending.allowedActions -join ', ')"
        $action = Read-Host "Enter an allowed action (approval is never automatic)"
        if ($pending.allowedActions -notcontains $action) {
            throw "The entered action is not allowed for this gate."
        }
        $comments = Read-Host "Enter review comments"
        $conditions = @()
        if ($action -eq "APPROVE_WITH_CONDITIONS") {
            $condition = Read-Host "Enter an approval condition"
            if (-not [string]::IsNullOrWhiteSpace($condition)) {
                $conditions = @($condition)
            }
        }
        $decision = @{
            gateType = $pending.gateType
            stateVersion = $pending.stateVersion
            action = $action
            comments = $comments
            conditions = $conditions
            decidedBy = if ([string]::IsNullOrWhiteSpace($env:USERNAME)) { "local-user" } else { $env:USERNAME }
        } | ConvertTo-Json
        $workflow = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/workflows/$($workflow.workflowId)/approvals/$($pending.approvalId)" -ContentType "application/json" -Body $decision
    }

    $artifacts = Invoke-RestMethod -Uri "$BaseUrl/api/v1/workflows/$($workflow.workflowId)/artifacts"
    $audit = Invoke-RestMethod -Uri "$BaseUrl/api/v1/workflows/$($workflow.workflowId)/audit"
    Write-Host "Workflow: $($workflow.workflowId); status: $($workflow.status)"
    Write-Host "Artifacts: $($artifacts.Count); audit events: $($audit.Count)"
} catch {
    Write-Error "Phase 4 OpenAI demo failed safely: $($_.Exception.Message)"
    exit 1
} finally {
    if ($null -ne $server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id
    }
}

