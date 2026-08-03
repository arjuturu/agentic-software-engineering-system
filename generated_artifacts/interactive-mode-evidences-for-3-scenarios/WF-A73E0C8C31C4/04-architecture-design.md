# Architecture Design

- Workflow ID: WF-A73E0C8C31C4
- Version: 1

## Structured Evidence

~~~json
{
  "api_design": [
    {
      "method_or_type": "POST",
      "name": "create URL with optional alias",
      "path_or_signature": "urls",
      "purpose": "Create a generated code or normalized custom alias."
    },
    {
      "method_or_type": "GET",
      "name": "redirect alias or generated code",
      "path_or_signature": "{short_code}",
      "purpose": "Resolve the shared short-code namespace."
    }
  ],
  "architecture_decisions": [
    {
      "alternatives": [
        "Separate alias table"
      ],
      "consequences": [
        "Aliases and generated codes cannot collide"
      ],
      "decision": "Reuse UrlMapping.short_code for aliases.",
      "rationale": "One unique namespace avoids a new model and migration."
    }
  ],
  "architecture_summary": "Repository-aware extension of the existing layered URL shortener with optional custom aliases in the existing short-code namespace.",
  "components": [
    {
      "dependencies": [
        "Pydantic"
      ],
      "interfaces": [
        "UrlCreate"
      ],
      "name": "Schemas",
      "responsibility": "Normalize and validate optional custom aliases."
    },
    {
      "dependencies": [
        "Repository"
      ],
      "interfaces": [
        "create_short_url"
      ],
      "name": "Service",
      "responsibility": "Persist aliases once and preserve bounded generated codes."
    },
    {
      "dependencies": [
        "Service"
      ],
      "interfaces": [
        "POST /api/v1/urls",
        "GET /{short_code}"
      ],
      "name": "API",
      "responsibility": "Map alias conflicts to the approved HTTP response."
    }
  ],
  "control_flow": [
    "Normalize and validate an optional alias",
    "Check the shared namespace",
    "Persist once or use bounded generated-code allocation",
    "Map only duplicate aliases to HTTP 409"
  ],
  "data_design": [
    {
      "constraints": [
        "short_code is unique"
      ],
      "entity": "UrlMapping",
      "fields": [
        "id",
        "original_url",
        "short_code"
      ],
      "purpose": "Store generated codes and aliases in one namespace.",
      "relationships": []
    }
  ],
  "implementation_feasible": true,
  "limitations": [
    "No analytics, expiration, authentication, ownership, alias management, or UI."
  ],
  "observability_controls": [
    "Existing validation and audit evidence"
  ],
  "reliability_controls": [
    "Database uniqueness remains authoritative",
    "Unexpected database failures propagate"
  ],
  "risks": [
    "Concurrent alias creation must distinguish duplicates from other failures."
  ],
  "security_controls": [
    "Reserved route values are blocked",
    "Task-scoped hash-guarded modifications"
  ],
  "status": "DESIGN_COMPLETE",
  "trade_offs": [
    "Lowercase normalization makes alias uniqueness case-insensitive."
  ]
}
~~~

## Evidence References

- WF-A73E0C8C31C4/04-architecture-design.json
