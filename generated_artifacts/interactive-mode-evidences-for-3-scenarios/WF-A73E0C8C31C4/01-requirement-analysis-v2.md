# Requirement Analysis

- Workflow ID: WF-A73E0C8C31C4
- Version: 2

## Structured Evidence

~~~json
{
  "acceptance_criteria": [
    "Missing custom_alias retains eight-character generated-code creation.",
    "Valid aliases are normalized, persisted, returned, and redirected.",
    "Invalid, reserved, and duplicate aliases return the approved responses.",
    "Existing URL validation, redirects, missing-code behavior, tests, and lint pass."
  ],
  "ambiguities": [],
  "assumptions": [
    "Q-ALIAS-001: optional",
    "Q-ALIAS-002: alphanumric",
    "Q-ALIAS-003: 5 to 9",
    "Q-ALIAS-004: Normalize aliases to lowercase before validation and persistence. Alias uniqueness is case-insensitive. Generated short codes and aliases share the same short_code namespace.",
    "Q-ALIAS-005: Custom Alias already used. Please try with new name.",
    "Q-ALIAS-006: Reserve api, docs, openapi.json, and health."
  ],
  "clarification_questions": [],
  "functional_requirements": [
    "Accept an optional custom_alias while preserving generated-code behavior.",
    "Trim and lowercase aliases, then enforce the approved syntax and length.",
    "Reject api, docs, openapi.json, and health as reserved aliases.",
    "Use the existing unique short_code namespace for aliases and generated codes.",
    "Return HTTP 409 with detail Custom alias already exists for duplicate aliases."
  ],
  "material_ambiguity": false,
  "non_functional_requirements": [
    "Preserve the existing FastAPI, SQLAlchemy, SQLite, Alembic, Pytest, and Ruff design.",
    "Use hash-guarded controlled modifications in a governed source copy."
  ],
  "normalized_requirement": "Add support for optional custom aliases.\r\nAliases should be user-friendly, unique, and handled safely. Optional aliases are lowercase, 4-30 characters, use lowercase letters, digits, hyphen, or underscore, share the short-code namespace, reserve api/docs/openapi.json/health, and return HTTP 409 for conflicts.",
  "risk_level": "MEDIUM",
  "risks": [
    "Alias and generated-code concurrency share one uniqueness constraint."
  ],
  "status": "READY_FOR_APPROVAL"
}
~~~

## Evidence References

- WF-A73E0C8C31C4/01-requirement-analysis-v2.json
