# Implementation Summary

- Workflow ID: WF-7989E1418EA9
- Version: 3

## Structured Evidence

~~~json
{
  "assumptions": [
    "Current repository hashes were supplied by the controlled context."
  ],
  "change_plan": [
    {
      "paths": [
        "app/schemas.py",
        "app/short_code_generator.py",
        "app/repository.py",
        "app/service.py"
      ],
      "task_id": "TASK-003"
    }
  ],
  "dependency_changes": [],
  "high_risk_change": false,
  "high_risk_reason": null,
  "implementation_summary": "Apply the deterministic task-scoped URL-shortener change.",
  "migrations_created": [],
  "replan_reason": null,
  "risks": [],
  "status": "READY_TO_APPLY",
  "structured_edits": [
    {
      "content": "from urllib.parse import urlsplit\n\nfrom pydantic import BaseModel, field_validator\n\n\nclass UrlCreate(BaseModel):\n    original_url: str\n\n    @field_validator(\"original_url\", mode=\"before\")\n    @classmethod\n    def validate_url(cls, value: object) -> str:\n        if not isinstance(value, str) or not value.strip():\n            raise ValueError(\"original_url must be a non-empty HTTP or HTTPS URL\")\n        normalized = value.strip()\n        parsed = urlsplit(normalized)\n        if parsed.scheme not in {\"http\", \"https\"} or not parsed.netloc:\n            raise ValueError(\"original_url must be an absolute HTTP or HTTPS URL\")\n        return normalized\n\n\nclass UrlResponse(BaseModel):\n    original_url: str\n    short_code: str\n    short_url: str\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "app/schemas.py",
      "replacement_text": null
    },
    {
      "content": "import secrets\nimport string\n\nALPHABET = string.ascii_letters + string.digits\n\n\ndef generate_short_code(length: int = 8) -> str:\n    return \"\".join(secrets.choice(ALPHABET) for _ in range(length))\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "app/short_code_generator.py",
      "replacement_text": null
    },
    {
      "content": "from sqlalchemy import select\nfrom sqlalchemy.orm import Session\n\nfrom app.models import UrlMapping\n\n\ndef find_by_code(session: Session, short_code: str) -> UrlMapping | None:\n    return session.scalar(select(UrlMapping).where(UrlMapping.short_code == short_code))\n\n\ndef create_mapping(session: Session, original_url: str, short_code: str) -> UrlMapping:\n    item = UrlMapping(original_url=original_url, short_code=short_code)\n    session.add(item)\n    session.commit()\n    session.refresh(item)\n    return item\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "app/repository.py",
      "replacement_text": null
    },
    {
      "content": "from collections.abc import Callable\n\nfrom sqlalchemy.exc import IntegrityError\nfrom sqlalchemy.orm import Session\n\nfrom app import repository\nfrom app.models import UrlMapping\nfrom app.short_code_generator import generate_short_code\n\n\nclass CollisionExhaustedError(Exception):\n    pass\n\n\ndef create_short_url(session: Session, original_url: str, code_factory: Callable[[], str] = generate_short_code) -> UrlMapping:\n    for _ in range(5):\n        code = code_factory()\n        if repository.find_by_code(session, code) is not None:\n            continue\n        try:\n            return repository.create_mapping(session, original_url, code)\n        except IntegrityError:\n            session.rollback()\n    raise CollisionExhaustedError\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "app/service.py",
      "replacement_text": null
    }
  ],
  "tests_created_or_modified": []
}
~~~

## Evidence References

- WF-7989E1418EA9/changes-v3.diff
