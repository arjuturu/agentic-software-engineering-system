# Code Change Plan

- Workflow ID: WF-A73E0C8C31C4
- Version: 2

## Structured Evidence

~~~json
{
  "assumptions": [
    "The existing short_code uniqueness constraint is authoritative."
  ],
  "change_plan": [
    {
      "paths": [
        "app/schemas.py",
        "app/short_code_generator.py"
      ],
      "task_id": "TASK-002"
    }
  ],
  "dependency_changes": [],
  "high_risk_change": false,
  "high_risk_reason": null,
  "implementation_summary": "Apply the clarified custom-alias change to current hash-guarded files.",
  "migrations_created": [],
  "replan_reason": null,
  "risks": [
    "Concurrent duplicate aliases are translated only after uniqueness evidence."
  ],
  "status": "READY_TO_APPLY",
  "structured_edits": [
    {
      "content": "import re\nfrom urllib.parse import urlsplit\n\nfrom pydantic import BaseModel, field_validator\n\nALIAS_PATTERN = re.compile(r\"^[a-z0-9_-]+$\")\nRESERVED_ALIASES = {\"api\", \"docs\", \"openapi.json\", \"health\"}\n\n\nclass UrlCreate(BaseModel):\n    original_url: str\n    custom_alias: str | None = None\n\n    @field_validator(\"original_url\", mode=\"before\")\n    @classmethod\n    def validate_url(cls, value: object) -> str:\n        if not isinstance(value, str) or not value.strip():\n            raise ValueError(\"original_url must be a non-empty HTTP or HTTPS URL\")\n        normalized = value.strip()\n        parsed = urlsplit(normalized)\n        if parsed.scheme not in {\"http\", \"https\"} or not parsed.netloc:\n            raise ValueError(\"original_url must be an absolute HTTP or HTTPS URL\")\n        return normalized\n\n    @field_validator(\"custom_alias\", mode=\"before\")\n    @classmethod\n    def validate_custom_alias(cls, value: object) -> str | None:\n        if value is None:\n            return None\n        if not isinstance(value, str):\n            raise ValueError(\"custom_alias must be a string\")\n        normalized = value.strip().lower()\n        if not 4 <= len(normalized) <= 30:\n            raise ValueError(\"custom_alias must contain between 4 and 30 characters\")\n        if normalized in RESERVED_ALIASES:\n            raise ValueError(\"custom_alias is reserved\")\n        if ALIAS_PATTERN.fullmatch(normalized) is None:\n            raise ValueError(\n                \"custom_alias may contain lowercase letters, digits, hyphen, and underscore\"\n            )\n        return normalized\n\n\nclass UrlResponse(BaseModel):\n    original_url: str\n    short_code: str\n    short_url: str\n",
      "expected_absent": false,
      "expected_hash": "245060073e59f6a3423c486c53aa6b6f8ad02b54bb5c2a6d93741de947c26efb",
      "old_text": null,
      "operation": "MODIFY",
      "relative_path": "app/schemas.py",
      "replacement_text": null
    },
    {
      "content": "import secrets\nimport string\n\nALPHABET = string.ascii_lowercase + string.digits\n\n\ndef generate_short_code(length: int = 8) -> str:\n    return \"\".join(secrets.choice(ALPHABET) for _ in range(length))\n",
      "expected_absent": false,
      "expected_hash": "4d54c57025f06b3451ee30510a6cff541809fe3d27f430964bb1a86a50bad6a1",
      "old_text": null,
      "operation": "MODIFY",
      "relative_path": "app/short_code_generator.py",
      "replacement_text": null
    }
  ],
  "tests_created_or_modified": []
}
~~~

## Evidence References

- WF-A73E0C8C31C4/07-code-change-plan-v2.json
