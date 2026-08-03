# Code Change Plan

- Workflow ID: WF-7989E1418EA9
- Version: 5

## Structured Evidence

~~~json
{
  "assumptions": [
    "Current repository hashes were supplied by the controlled context."
  ],
  "change_plan": [
    {
      "paths": [
        "tests/conftest.py",
        "tests/test_api.py",
        "tests/test_service.py"
      ],
      "task_id": "TASK-005"
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
      "content": "import pytest\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import sessionmaker\n\nfrom app.database import Base, get_db\nfrom app.main import app\n\n\n@pytest.fixture\ndef client(tmp_path):\n    engine = create_engine(f\"sqlite:///{tmp_path / 'test.db'}\", connect_args={\"check_same_thread\": False})\n    sessions = sessionmaker(bind=engine, expire_on_commit=False)\n    Base.metadata.create_all(engine)\n\n    def override_db():\n        with sessions() as session:\n            yield session\n\n    app.dependency_overrides[get_db] = override_db\n    with TestClient(app) as test_client:\n        yield test_client\n    app.dependency_overrides.clear()\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "tests/conftest.py",
      "replacement_text": null
    },
    {
      "content": "def test_create_and_redirect(client):\n    created = client.post(\"/api/v1/urls\", json={\"original_url\": \"  https://example.com/path  \"})\n    assert created.status_code == 201\n    body = created.json()\n    assert body[\"original_url\"] == \"https://example.com/path\"\n    assert len(body[\"short_code\"]) == 8\n    redirected = client.get(f\"/{body['short_code']}\", follow_redirects=False)\n    assert redirected.status_code == 307\n    assert redirected.headers[\"location\"] == \"https://example.com/path\"\n\n\ndef test_invalid_and_missing_urls(client):\n    assert client.post(\"/api/v1/urls\", json={\"original_url\": \"not-a-url\"}).status_code == 422\n    missing = client.get(\"/UNKNOWN\", follow_redirects=False)\n    assert missing.status_code == 404\n    assert missing.json() == {\"detail\": \"Short URL not found\"}\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "tests/test_api.py",
      "replacement_text": null
    },
    {
      "content": "import pytest\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import Session\n\nfrom app.database import Base\nfrom app.service import CollisionExhaustedError, create_short_url\n\n\ndef test_generated_codes_are_unique(tmp_path):\n    engine = create_engine(f\"sqlite:///{tmp_path / 'unique.db'}\")\n    Base.metadata.create_all(engine)\n    with Session(engine, expire_on_commit=False) as session:\n        first = create_short_url(session, \"https://example.com/one\")\n        second = create_short_url(session, \"https://example.com/two\")\n    assert first.short_code != second.short_code\n    assert len(first.short_code) == len(second.short_code) == 8\n\n\ndef test_collision_retry_is_bounded(tmp_path):\n    engine = create_engine(f\"sqlite:///{tmp_path / 'collision.db'}\")\n    Base.metadata.create_all(engine)\n    attempts = 0\n\n    def collision() -> str:\n        nonlocal attempts\n        attempts += 1\n        return \"COLLIDE1\"\n\n    with Session(engine, expire_on_commit=False) as session:\n        create_short_url(session, \"https://example.com/original\", collision)\n        attempts = 0\n        with pytest.raises(CollisionExhaustedError):\n            create_short_url(session, \"https://example.com/duplicate\", collision)\n    assert attempts == 5\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "tests/test_service.py",
      "replacement_text": null
    }
  ],
  "tests_created_or_modified": [
    "tests/conftest.py",
    "tests/test_api.py",
    "tests/test_service.py"
  ]
}
~~~

## Evidence References

- WF-7989E1418EA9/07-code-change-plan-v5.json
