# API and Schema Contracts

## Control-plane API

All workflow responses use app/schemas/workflows.py. Validation errors return the standard safe
error envelope and never expose stack traces.

| Method and path | Purpose | Request | Response and transition | Major errors |
| --- | --- | --- | --- | --- |
| GET / | Service metadata | None | Name, version, docs path | Internal error envelope |
| GET /health/live | Process liveness | None | status UP | None under normal import |
| GET /health/ready | Required dependency checks | None | Component UP/DOWN; HTTP 503 if mandatory check fails | Safe component status only |
| POST /api/v1/workflows | Start workflow | WorkflowCreateRequest | HTTP 201 WorkflowResponse; may pause at clarification/approval | Pydantic 422, invalid source/policy |
| GET /api/v1/workflows/{workflow_id} | Current durable snapshot | Path ID | WorkflowResponse | WORKFLOW_NOT_FOUND |
| POST /api/v1/workflows/{workflow_id}/clarifications | Resume clarification | ClarificationSubmitRequest | WorkflowResponse after re-analysis | NOT_FOUND, ALREADY_SUBMITTED, INVALID_STATE_VERSION, invalid question IDs |
| POST /api/v1/workflows/{workflow_id}/approvals/{approval_id} | Resume human gate | ApprovalSubmitRequest | WorkflowResponse after selected transition | NOT_FOUND, ALREADY_COMPLETED, gate/version/action mismatch |
| POST /api/v1/workflows/{workflow_id}/retry | Controlled legacy retry | Path ID | WorkflowResponse | WORKFLOW_NOT_RETRYABLE |
| GET /api/v1/workflows/{workflow_id}/artifacts | Artifact metadata | Path ID | ArtifactRecordResponse list | WORKFLOW_NOT_FOUND |
| GET /api/v1/workflows/{workflow_id}/artifacts/{file_name} | Read governed artifact | IDs | ArtifactContentResponse | Not found/path policy |
| GET /api/v1/workflows/{workflow_id}/audit | Ordered audit history | Path ID | AuditEventResponse list | WORKFLOW_NOT_FOUND |

WorkflowCreateRequest requires scenarioType, a 1–10,000 character requirement, and a constrained
workspaceName. Brownfield and Ambiguous also require sourceWorkspace. SourceWorkspace is a
workspace directory name relative to WORKSPACE_ROOT.

Clarification submissions include type CLARIFICATION_RESPONSE, workflowId, clarificationId,
stateVersion, and non-empty questionId/answer pairs. Approval submissions include gateType,
stateVersion, action, comments, conditions, and decidedBy.

## Generated Greenfield application

Source: workspace/phase6-interactive/phase6-interactive-greenfield-20260803182759430.

| Route | Contract |
| --- | --- |
| POST /api/v1/urls | UrlCreate {original_url}; trims and validates absolute HTTP(S); HTTP 201 UrlResponse |
| GET /{short_code} | HTTP 307 redirect; HTTP 404 detail Short URL not found |

UrlResponse contains original_url, short_code, and request-derived short_url. Allocation uses
eight-character alphanumeric secrets with at most five collision retries; exhaustion maps to HTTP
503 detail Unable to generate a unique short code.

## Generated Brownfield analytics application

Selected source: workspace/phase6-interactive/phase6-interactive-brownfield-20260803191133045.

| Route | Contract |
| --- | --- |
| POST /api/v1/urls | Preserved Greenfield creation contract |
| GET /{short_code} | Atomically increments click_count and returns HTTP 307 |
| GET /api/v1/urls/{short_code}/stats | UrlStatsResponse including click_count; unknown code is HTTP 404 |

The 0002_add_click_count migration adds the persisted counter with default zero.

## Generated Ambiguous alias application

Source: workspace/phase6-interactive/phase6-interactive-ambiguous-20260803194502236.

| Route | Contract |
| --- | --- |
| POST /api/v1/urls | UrlCreate accepts optional custom_alias; HTTP 201, conflict HTTP 409 |
| GET /{short_code} | Existing alias or generated code redirects with HTTP 307; unknown value HTTP 404 |

The implemented schema strips and lowercases aliases, accepts 4–30 lowercase letters, digits,
hyphens, or underscores, and reserves api, docs, openapi.json, and health. Aliases and generated
codes share the short_code namespace. The generated model/repository supports this without a new
migration.
