param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$UseExistingServer
)

$ErrorActionPreference = "Stop"
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

    Write-Host "OFFLINE SCRIPTED PLATFORM TEST DOUBLE — not the real Phase 4 OpenAI acceptance run"
    $request = @{
        scenarioType = "GREENFIELD"
        requirement = "Build a production-style local URL shortening API with short codes, optional aliases, redirects, expiration, analytics, health endpoints, SQLite, SQLAlchemy, Alembic, tests, and documentation."
        workspaceName = "phase4-scripted-demo"
        scriptedScenario = "HAPPY_PATH"
    } | ConvertTo-Json
    $workflow = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/workflows" -ContentType "application/json" -Body $request

    while ($workflow.pendingApproval.approvalId) {
        $pending = $workflow.pendingApproval
        $decision = @{
            gateType = $pending.gateType
            stateVersion = $pending.stateVersion
            action = "APPROVE"
            comments = "Automated approval for the offline scripted platform test double only."
            conditions = @()
            decidedBy = "phase4-scripted-demo"
        } | ConvertTo-Json
        $workflow = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/workflows/$($workflow.workflowId)/approvals/$($pending.approvalId)" -ContentType "application/json" -Body $decision
    }

    $artifacts = Invoke-RestMethod -Uri "$BaseUrl/api/v1/workflows/$($workflow.workflowId)/artifacts"
    $audit = Invoke-RestMethod -Uri "$BaseUrl/api/v1/workflows/$($workflow.workflowId)/audit"
    Write-Host "Workflow: $($workflow.workflowId)"
    Write-Host "Status: $($workflow.status)"
    Write-Host "Scenario profile: $($workflow.scenarioProfile.profile_id)"
    Write-Host "Artifacts: $($artifacts.Count); audit events: $($audit.Count)"
    Write-Host "Contract status: NOT EXECUTED (SCRIPTED_PLATFORM_TEST_DOUBLE)"
} catch {
    Write-Error "Phase 4 scripted demo failed: $($_.Exception.Message)"
    exit 1
} finally {
    if ($null -ne $server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id
    }
}
