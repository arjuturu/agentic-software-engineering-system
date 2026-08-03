param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [ValidateSet("Automatic", "Interactive")]
    [string]$Mode = "Automatic",
    [ValidateSet("Greenfield", "Brownfield", "Ambiguous", "All")]
    [string]$Scenario = "All",
    [switch]$UseExistingServer,
    [string]$WorkspacePrefix = "phase4-scripted-demo",
    [string]$SourceWorkspace = "",
    [ValidateRange(1, 3600)]
    [int]$MaxPollAttempts = 600,
    [ValidateRange(50, 10000)]
    [int]$PollIntervalMilliseconds = 500
)

$ErrorActionPreference = "Stop"
$BaseUrl = $BaseUrl.TrimEnd("/")
$TerminalStatuses = @(
    "READY",
    "READY_WITH_CONDITIONS",
    "NOT_READY",
    "FAILED",
    "CANCELLED",
    "SAFE_STOPPED",
    "ROLLBACK_COMPLETE"
)
$FailureStatuses = @(
    "READY_WITH_CONDITIONS",
    "NOT_READY",
    "FAILED",
    "CANCELLED",
    "SAFE_STOPPED",
    "ROLLBACK_COMPLETE"
)
$AliasDefaults = @{
    "Q-ALIAS-001" = "The custom alias is optional. When omitted, retain the existing generated short-code behavior."
    "Q-ALIAS-002" = "Allow lowercase letters, digits, hyphen, and underscore only."
    "Q-ALIAS-003" = "Aliases must contain between 4 and 30 characters."
    "Q-ALIAS-004" = "Normalize aliases to lowercase before validation and persistence. Alias uniqueness is case-insensitive. Generated short codes and aliases share the same short_code namespace."
    "Q-ALIAS-005" = 'Return HTTP 409 with exactly {"detail":"Custom alias already exists"}.'
    "Q-ALIAS-006" = "Reserve api, docs, openapi.json, and health."
}

$GreenfieldRequirement = @"
Build a local URL-shortening API using FastAPI, SQLite, SQLAlchemy 2.x, and Alembic.
Support POST /api/v1/urls and GET /{short_code}.
Generate secure eight-character alphanumeric short codes using Python secrets.
Retry collisions no more than five times.
Return the approved exact 404 and 503 responses.
Include tests and documentation.
Do not add aliases, analytics, expiration, authentication, caching, UI, messaging, workers, or cloud deployment.
"@

$BrownfieldRequirement = @"
Enhance the existing URL-shortener application with click analytics.
Add a click_count column with a default value of 0.
Increment click_count on every successful redirect.
Add GET /api/v1/urls/{short_code}/stats.
Create a new Alembic migration.
Preserve existing creation, validation, collision, and redirect behavior.
Add regression tests.
Do not add aliases, expiration, authentication, caching, messaging, workers, UI, or cloud deployment.
"@

$AmbiguousRequirement = @"
Add support for optional custom aliases.
Aliases should be user-friendly, unique, and handled safely.
"@

function Wait-ForServer {
    param([int]$Attempts = 60)

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $live = Invoke-RestMethod -Uri "$BaseUrl/health/live" -TimeoutSec 2
            $ready = Invoke-RestMethod -Uri "$BaseUrl/health/ready" -TimeoutSec 2
            if ($live.status -eq "UP" -and $ready.status -eq "UP") {
                Write-Host "Server is live and ready at $BaseUrl."
                return
            }
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw "The API did not become ready at $BaseUrl after $Attempts attempts."
            }
        }
        Start-Sleep -Milliseconds 500
    }
    throw "The API did not become ready at $BaseUrl."
}

function New-ScriptedWorkflow {
    param(
        [string]$ScenarioType,
        [string]$ScriptedScenario,
        [string]$Requirement,
        [string]$WorkspaceName,
        [string]$SourceWorkspaceName = ""
    )

    $request = [ordered]@{
        scenarioType = $ScenarioType
        scriptedScenario = $ScriptedScenario
        requirement = $Requirement
        workspaceName = $WorkspaceName
    }
    if (-not [string]::IsNullOrWhiteSpace($SourceWorkspaceName)) {
        $request.sourceWorkspace = $SourceWorkspaceName
    }
    Write-Host ""
    Write-Host "Creating $ScenarioType workflow in workspace '$WorkspaceName'..."
    $invoke = @{
        Method = "Post"
        Uri = "$BaseUrl/api/v1/workflows"
        ContentType = "application/json"
        Body = ($request | ConvertTo-Json -Depth 10)
    }
    return Invoke-RestMethod @invoke
}

function Get-WorkflowState {
    param([string]$WorkflowId)

    return Invoke-RestMethod -Uri "$BaseUrl/api/v1/workflows/$WorkflowId"
}

function Get-WorkflowArtifacts {
    param([string]$WorkflowId)

    return @(Invoke-RestMethod -Uri "$BaseUrl/api/v1/workflows/$WorkflowId/artifacts")
}

function Get-WorkflowAudit {
    param([string]$WorkflowId)

    return @(Invoke-RestMethod -Uri "$BaseUrl/api/v1/workflows/$WorkflowId/audit")
}

function Show-HighRiskEvidence {
    param([object]$Workflow)

    if ($Workflow.pendingApproval.gateType -ne "HIGH_RISK_CHANGE") {
        return
    }
    try {
        $audit = Get-WorkflowAudit -WorkflowId $Workflow.workflowId
        $selection = @(
            $audit | Where-Object { $_.eventType -eq "CODING_TASK_SELECTED" }
        ) | Select-Object -Last 1
        $changePlan = @(
            $audit | Where-Object { $_.eventType -eq "CHANGE_PLAN_CREATED" }
        ) | Select-Object -Last 1
        if ($null -ne $selection) {
            Write-Host "Task ID: $($selection.details.task_id)"
        }
        if ($null -ne $changePlan) {
            Write-Host "Edit count: $($changePlan.details.edit_count)"
        }
        $artifacts = Get-WorkflowArtifacts -WorkflowId $Workflow.workflowId
        $changeArtifacts = @(
            $artifacts | Where-Object {
                $_.fileName -like "07-code-change-plan*" -or
                $_.fileName -like "*migration*"
            } | ForEach-Object { $_.fileName }
        )
        if ($changeArtifacts.Count -gt 0) {
            Write-Host "Change or migration evidence: $($changeArtifacts -join ', ')"
        }
    }
    catch {
        Write-Host "Optional high-risk evidence is unavailable."
    }
}

function Submit-Approval {
    param(
        [object]$Workflow,
        [string]$DriverMode,
        [string]$ScenarioName
    )

    $pending = $Workflow.pendingApproval
    $allowedActions = @($pending.allowedActions)
    if ([string]::IsNullOrWhiteSpace([string]$pending.approvalId)) {
        throw "No pending approval ID is available for workflow $($Workflow.workflowId)."
    }

    Write-Host ""
    Write-Host "Approval gate observed"
    Write-Host "Scenario: $ScenarioName"
    Write-Host "Workflow ID: $($Workflow.workflowId)"
    Write-Host "Current stage: $($Workflow.currentStage)"
    Write-Host "Gate type: $($pending.gateType)"
    Write-Host "Approval ID: $($pending.approvalId)"
    Write-Host "State version: $($pending.stateVersion)"
    Write-Host "Allowed actions: $($allowedActions -join ', ')"

    $action = "APPROVE"
    $comments = "Automatic governed approval for $ScenarioName at gate $($pending.gateType)."
    $conditions = @()
    $decidedBy = "phase4-scripted-demo-automatic"

    if ($DriverMode -eq "Interactive") {
        Write-Host "Architecture version: $($Workflow.architectureVersion)"
        Write-Host "Plan version: $($Workflow.planVersion)"
        Write-Host "Retry counts: $($Workflow.retryCounts | ConvertTo-Json -Compress)"
        Show-HighRiskEvidence -Workflow $Workflow

        $choices = [ordered]@{
            "1" = "APPROVE"
            "2" = "APPROVE_WITH_CONDITIONS"
            "3" = "REQUEST_CHANGES"
            "4" = "REJECT"
        }
        do {
            Write-Host "Available decisions:"
            foreach ($choice in $choices.GetEnumerator()) {
                if ($allowedActions -contains $choice.Value) {
                    Write-Host "$($choice.Key). $($choice.Value)"
                }
            }
            $selected = Read-Host "Select an allowed action"
            $action = $choices[$selected]
        } until ($null -ne $action -and $allowedActions -contains $action)

        $decidedBy = "phase4-scripted-demo-interactive"
        switch ($action) {
            "APPROVE_WITH_CONDITIONS" {
                $conditionText = Read-Host "Enter one or more semicolon-separated conditions"
                $conditions = @(
                    $conditionText.Split(
                        ";",
                        [System.StringSplitOptions]::RemoveEmptyEntries
                    ) | ForEach-Object { $_.Trim() }
                )
                if ($conditions.Count -eq 0) {
                    throw "APPROVE_WITH_CONDITIONS requires at least one condition."
                }
                $comments = "Interactive approval with conditions."
            }
            "REQUEST_CHANGES" {
                $comments = Read-Host "Describe the requested changes"
                if ([string]::IsNullOrWhiteSpace($comments)) {
                    throw "REQUEST_CHANGES requires comments."
                }
            }
            "REJECT" {
                $confirmation = Read-Host "Type REJECT to confirm"
                if ($confirmation -ne "REJECT") {
                    throw "Rejection was not confirmed."
                }
                $comments = Read-Host "Enter rejection comments"
            }
            default {
                $comments = Read-Host "Optional approval comments"
                if ([string]::IsNullOrWhiteSpace($comments)) {
                    $comments = "Interactive governed approval."
                }
            }
        }
    }
    elseif ($allowedActions -notcontains "APPROVE") {
        throw "APPROVE is not allowed for approval $($pending.approvalId)."
    }

    $decision = [ordered]@{
        gateType = $pending.gateType
        stateVersion = $pending.stateVersion
        action = $action
        comments = $comments
        conditions = @($conditions)
        decidedBy = $decidedBy
    }
    $invoke = @{
        Method = "Post"
        Uri = "$BaseUrl/api/v1/workflows/$($Workflow.workflowId)/approvals/$($pending.approvalId)"
        ContentType = "application/json"
        Body = ($decision | ConvertTo-Json -Depth 10)
    }
    return Invoke-RestMethod @invoke
}

function Submit-Clarification {
    param(
        [object]$Workflow,
        [string]$DriverMode,
        [string]$ScenarioName
    )

    $pending = $Workflow.pendingInteraction.payload
    if ([string]::IsNullOrWhiteSpace([string]$pending.clarificationId)) {
        throw "No clarification ID is available for workflow $($Workflow.workflowId)."
    }
    Write-Host ""
    Write-Host "Clarification observed for $ScenarioName"
    Write-Host "Workflow ID: $($Workflow.workflowId)"
    Write-Host "Clarification ID: $($pending.clarificationId)"
    Write-Host "State version: $($pending.stateVersion)"

    $answers = @()
    foreach ($question in @($pending.questions)) {
        $questionId = [string]$question.question_id
        $defaultAnswer = [string]$AliasDefaults[$questionId]
        if ([string]::IsNullOrWhiteSpace($defaultAnswer)) {
            throw "No deterministic clarification answer exists for $questionId."
        }
        Write-Host ""
        Write-Host "$questionId"
        Write-Host $question.question
        Write-Host "Default: $defaultAnswer"
        $answer = $defaultAnswer
        if ($DriverMode -eq "Interactive") {
            $replacement = Read-Host "Press Enter to use the default, or type a replacement answer"
            if (-not [string]::IsNullOrWhiteSpace($replacement)) {
                $answer = $replacement
            }
        }
        $answers += [ordered]@{
            questionId = $questionId
            answer = $answer
        }
    }

    $clarification = [ordered]@{
        workflowId = $Workflow.workflowId
        clarificationId = $pending.clarificationId
        stateVersion = $pending.stateVersion
        answers = $answers
    }
    $invoke = @{
        Method = "Post"
        Uri = "$BaseUrl/api/v1/workflows/$($Workflow.workflowId)/clarifications"
        ContentType = "application/json"
        Body = ($clarification | ConvertTo-Json -Depth 10)
    }
    $response = Invoke-RestMethod @invoke
    if ($response.status -eq "WAITING_FOR_CLARIFICATION") {
        throw "Workflow $($Workflow.workflowId) did not accept the clarification response."
    }
    return $response
}

function Test-TerminalWorkflow {
    param([object]$Workflow)

    return (
        $TerminalStatuses -contains [string]$Workflow.status -or
        $Workflow.currentStage -eq "ROLLBACK_COMPLETE"
    )
}

function Invoke-WorkflowUntilTerminal {
    param(
        [object]$Workflow,
        [string]$DriverMode,
        [string]$ScenarioName
    )

    for ($attempt = 1; $attempt -le $MaxPollAttempts; $attempt++) {
        $Workflow = Get-WorkflowState -WorkflowId $Workflow.workflowId
        Write-Host (
            "[$ScenarioName] status=$($Workflow.status) " +
            "stage=$($Workflow.currentStage) stateVersion=$($Workflow.stateVersion)"
        )

        if (
            $Workflow.pendingInteraction.type -eq "CLARIFICATION" -and
            $null -ne $Workflow.pendingInteraction.payload
        ) {
            $Workflow = Submit-Clarification -Workflow $Workflow -DriverMode $DriverMode -ScenarioName $ScenarioName
            continue
        }
        if (-not [string]::IsNullOrWhiteSpace(
            [string]$Workflow.pendingApproval.approvalId
        )) {
            $Workflow = Submit-Approval -Workflow $Workflow -DriverMode $DriverMode -ScenarioName $ScenarioName
            continue
        }
        if (Test-TerminalWorkflow -Workflow $Workflow) {
            return $Workflow
        }
        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    }
    throw (
        "Workflow $($Workflow.workflowId) timed out after " +
        "$MaxPollAttempts polling attempts."
    )
}

function Assert-ScenarioEvidence {
    param(
        [object]$Workflow,
        [string]$ScenarioName,
        [string]$ExpectedProfile,
        [string]$ExpectedSource = ""
    )

    if ($Workflow.status -ne "READY") {
        throw (
            "$ScenarioName workflow $($Workflow.workflowId) ended with " +
            "status $($Workflow.status) and stage $($Workflow.currentStage)."
        )
    }
    $artifacts = Get-WorkflowArtifacts -WorkflowId $Workflow.workflowId
    $audit = Get-WorkflowAudit -WorkflowId $Workflow.workflowId
    $validation = @(
        $audit | Where-Object {
            $_.eventType -eq "VALIDATION_COMPLETED" -and
            $_.details.status -eq "VALIDATION_PASSED"
        }
    )
    if ($validation.Count -ne 1) {
        throw "$ScenarioName does not have exactly one passing final validation event."
    }
    if ($Workflow.scenarioProfile.profile_id -ne $ExpectedProfile) {
        throw (
            "$ScenarioName used profile $($Workflow.scenarioProfile.profile_id); " +
            "expected $ExpectedProfile."
        )
    }

    if (-not [string]::IsNullOrWhiteSpace($ExpectedSource)) {
        $sourceEvents = @(
            $audit | Where-Object {
                $_.eventType -eq "BROWNFIELD_SOURCE_VALIDATED" -and
                $_.details.source_workspace -eq $ExpectedSource
            }
        )
        if ($sourceEvents.Count -ne 1) {
            throw "$ScenarioName does not identify Greenfield source '$ExpectedSource'."
        }
        if ($Workflow.workspacePath -eq $ExpectedSource) {
            throw "$ScenarioName destination must differ from its Greenfield source."
        }
    }

    if ($ScenarioName -eq "Brownfield") {
        $repositoryIndex = -1
        $designIndex = -1
        $planningIndex = -1
        for ($index = 0; $index -lt $audit.Count; $index++) {
            $event = $audit[$index]
            if (
                $event.eventType -eq "AGENT_STARTED" -and
                $event.stage -eq "REPOSITORY_ANALYSIS"
            ) {
                $repositoryIndex = $index
            }
            elseif ($event.eventType -eq "AGENT_STARTED" -and $event.stage -eq "DESIGN") {
                $designIndex = $index
            }
            elseif ($event.eventType -eq "AGENT_STARTED" -and $event.stage -eq "PLANNING") {
                $planningIndex = $index
            }
        }
        if (
            $repositoryIndex -lt 0 -or
            $designIndex -le $repositoryIndex -or
            $planningIndex -le $designIndex
        ) {
            throw "Brownfield repository analysis did not precede Design and Planning."
        }
    }

    if ($ScenarioName -eq "Ambiguous") {
        $requested = @(
            $audit | Where-Object { $_.eventType -eq "CLARIFICATION_REQUESTED" }
        )
        $submitted = @(
            $audit | Where-Object { $_.eventType -eq "CLARIFICATION_SUBMITTED" }
        )
        if ($requested.Count -ne 1 -or $submitted.Count -ne 1) {
            throw "Ambiguous workflow clarification evidence is incomplete."
        }
    }

    $duration = ""
    if ($null -ne $Workflow.startedAt -and $null -ne $Workflow.completedAt) {
        $started = [DateTimeOffset]::Parse([string]$Workflow.startedAt)
        $completed = [DateTimeOffset]::Parse([string]$Workflow.completedAt)
        $duration = [Math]::Round(($completed - $started).TotalSeconds, 2)
    }
    $planningRetries = 0
    $codingRetries = 0
    if ($null -ne $Workflow.retryCounts.planning) {
        $planningRetries = $Workflow.retryCounts.planning
    }
    if ($null -ne $Workflow.retryCounts.coding) {
        $codingRetries = $Workflow.retryCounts.coding
    }
    return [PSCustomObject]@{
        Scenario = $ScenarioName
        WorkflowId = $Workflow.workflowId
        SourceWorkspace = $(if ($ExpectedSource) { $ExpectedSource } else { "-" })
        DestinationWorkspace = $Workflow.workspacePath
        Status = $Workflow.status
        RequirementVersion = $Workflow.requirementVersion
        ArchitectureVersion = $Workflow.architectureVersion
        PlanVersion = $Workflow.planVersion
        PlanningRetries = $planningRetries
        CodingRetries = $codingRetries
        FinalReleaseStatus = $Workflow.finalReleaseStatus
        StartedAt = $Workflow.startedAt
        CompletedAt = $Workflow.completedAt
        DurationSeconds = $duration
        ArtifactCount = $artifacts.Count
        AuditEventCount = $audit.Count
        RollbackStatus = $(if ($Workflow.currentStage -eq "ROLLBACK_COMPLETE") {
            "ROLLBACK_COMPLETE"
        }
        else {
            "NOT_TRIGGERED"
        })
    }
}

$server = $null
$exitCode = 0
$summaries = @()
try {
    Write-Host "Deterministic scripted URL-shortener demonstration."
    Write-Host (
        "LLM responses are scripted; orchestration, approvals, editing, Git, validation, " +
        "retries, rollback, and audit execution remain real."
    )
    Write-Host "Expected provider mode: SCRIPTED"
    if (
        -not [string]::IsNullOrWhiteSpace($env:LLM_MODE) -and
        $env:LLM_MODE.ToUpperInvariant() -ne "SCRIPTED"
    ) {
        throw "LLM_MODE must be SCRIPTED for this demonstration."
    }

    $baseUri = [Uri]$BaseUrl
    if ($baseUri.Scheme -notin @("http", "https")) {
        throw "BaseUrl must use HTTP or HTTPS."
    }
    if (-not $UseExistingServer -and $baseUri.Scheme -ne "http") {
        throw "The built-in Uvicorn startup supports HTTP BaseUrl values only."
    }

    if (-not $UseExistingServer) {
        $repositoryRoot = Split-Path -Parent $PSScriptRoot
        $venvPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
        $pythonExecutable = $(if (Test-Path -LiteralPath $venvPython) {
            $venvPython
        }
        else {
            "python"
        })
        Write-Host "Starting Uvicorn on host $($baseUri.Host), port $($baseUri.Port)..."
        $start = @{
            FilePath = $pythonExecutable
            ArgumentList = @(
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                $baseUri.Host,
                "--port",
                [string]$baseUri.Port
            )
            WorkingDirectory = $repositoryRoot
            PassThru = $true
            WindowStyle = "Hidden"
        }
        $server = Start-Process @start
    }
    Wait-ForServer

    $timestamp = Get-Date -Format "yyyyMMddHHmmssfff"
    $greenWorkspace = "$WorkspacePrefix-greenfield-$timestamp"
    $brownWorkspace = "$WorkspacePrefix-brownfield-$timestamp"
    $ambiguousWorkspace = "$WorkspacePrefix-ambiguous-$timestamp"
    $greenSource = $SourceWorkspace
    $runGreenfield = (
        $Scenario -in @("Greenfield", "All") -or
        (
            $Scenario -in @("Brownfield", "Ambiguous") -and
            [string]::IsNullOrWhiteSpace($SourceWorkspace)
        )
    )

    if ($runGreenfield) {
        $green = New-ScriptedWorkflow -ScenarioType "GREENFIELD" -ScriptedScenario "URL_SHORTENER_GREENFIELD_HAPPY_PATH" -Requirement $GreenfieldRequirement -WorkspaceName $greenWorkspace
        $green = Invoke-WorkflowUntilTerminal -Workflow $green -DriverMode $Mode -ScenarioName "Greenfield"
        $summaries += Assert-ScenarioEvidence -Workflow $green -ScenarioName "Greenfield" -ExpectedProfile "URL_SHORTENER_GREENFIELD"
        $greenSource = $green.workspacePath
    }

    if ($Scenario -in @("Brownfield", "All")) {
        if ([string]::IsNullOrWhiteSpace($greenSource)) {
            throw "Brownfield requires a successful Greenfield source workspace."
        }
        $brown = New-ScriptedWorkflow -ScenarioType "BROWNFIELD" -ScriptedScenario "URL_SHORTENER_BROWNFIELD_ANALYTICS" -Requirement $BrownfieldRequirement -WorkspaceName $brownWorkspace -SourceWorkspaceName $greenSource
        $brown = Invoke-WorkflowUntilTerminal -Workflow $brown -DriverMode $Mode -ScenarioName "Brownfield"
        $summaries += Assert-ScenarioEvidence -Workflow $brown -ScenarioName "Brownfield" -ExpectedProfile "URL_SHORTENER_BROWNFIELD" -ExpectedSource $greenSource
    }

    if ($Scenario -in @("Ambiguous", "All")) {
        if ([string]::IsNullOrWhiteSpace($greenSource)) {
            throw "Ambiguous aliases require a successful Greenfield source workspace."
        }
        $ambiguous = New-ScriptedWorkflow -ScenarioType "AMBIGUOUS" -ScriptedScenario "URL_SHORTENER_AMBIGUOUS_ALIASES" -Requirement $AmbiguousRequirement -WorkspaceName $ambiguousWorkspace -SourceWorkspaceName $greenSource
        $ambiguous = Invoke-WorkflowUntilTerminal -Workflow $ambiguous -DriverMode $Mode -ScenarioName "Ambiguous"
        if ($null -ne $brown -and $ambiguous.workspacePath -eq $brown.workspacePath) {
            throw "Brownfield and Ambiguous must use separate destination workspaces."
        }
        $summaries += Assert-ScenarioEvidence -Workflow $ambiguous -ScenarioName "Ambiguous" -ExpectedProfile "URL_SHORTENER_AMBIGUOUS_ALIASES" -ExpectedSource $greenSource
    }

    if (@($summaries | Where-Object { $FailureStatuses -contains $_.Status }).Count -gt 0) {
        throw "One or more selected scenarios ended in a failure state."
    }
    Write-Host ""
    Write-Host "Scenario summary"
    $summaries | Format-Table Scenario, WorkflowId, SourceWorkspace, DestinationWorkspace, Status -AutoSize -Wrap
    Write-Host ""
    foreach ($summary in $summaries) {
        Write-Host (
            "$($summary.Scenario): requirementVersion=$($summary.RequirementVersion); " +
            "architectureVersion=$($summary.ArchitectureVersion); " +
            "planVersion=$($summary.PlanVersion); " +
            "planningRetries=$($summary.PlanningRetries); " +
            "codingRetries=$($summary.CodingRetries); " +
            "finalReleaseStatus=$($summary.FinalReleaseStatus); " +
            "startedAt=$($summary.StartedAt); completedAt=$($summary.CompletedAt); " +
            "durationSeconds=$($summary.DurationSeconds); " +
            "artifacts=$($summary.ArtifactCount); auditEvents=$($summary.AuditEventCount); " +
            "rollbackStatus=$($summary.RollbackStatus)"
        )
    }
}
catch {
    Write-Host "Phase 4 scripted demo failed: $($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
}
finally {
    if ($null -ne $server -and -not $server.HasExited) {
        Write-Host "Stopping Uvicorn process $($server.Id)."
        Stop-Process -Id $server.Id
    }
}

exit $exitCode
