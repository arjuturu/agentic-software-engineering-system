# Code Change Plan

- Workflow ID: WF-7989E1418EA9
- Version: 1

## Structured Evidence

~~~json
{
  "assumptions": [
    "Current repository hashes were supplied by the controlled context."
  ],
  "change_plan": [
    {
      "paths": [
        "pyproject.toml",
        "requirements.txt",
        ".gitignore",
        "alembic.ini"
      ],
      "task_id": "TASK-001"
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
      "content": "[project]\nname = \"scripted-url-shortener\"\nversion = \"0.1.0\"\nrequires-python = \">=3.11\"\ndependencies = [\"fastapi\", \"sqlalchemy\", \"alembic\", \"pydantic\"]\n\n[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n\n[tool.ruff]\nline-length = 100\ntarget-version = \"py311\"\n\n[tool.ruff.lint]\nselect = [\"E\", \"F\", \"I\", \"B\", \"UP\"]\nignore = [\"E501\"]\n\n[tool.ruff.lint.per-file-ignores]\n\"app/api/*.py\" = [\"B008\"]\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "pyproject.toml",
      "replacement_text": null
    },
    {
      "content": "fastapi\nsqlalchemy\nalembic\npydantic\npytest\nhttpx\nruff\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "requirements.txt",
      "replacement_text": null
    },
    {
      "content": ".venv/\n__pycache__/\n*.pyc\n.pytest_cache/\n.ruff_cache/\n*.db\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": ".gitignore",
      "replacement_text": null
    },
    {
      "content": "[alembic]\nscript_location = alembic\nsqlalchemy.url = sqlite:///./url_shortener.db\n",
      "expected_absent": true,
      "expected_hash": null,
      "old_text": null,
      "operation": "CREATE",
      "relative_path": "alembic.ini",
      "replacement_text": null
    }
  ],
  "tests_created_or_modified": []
}
~~~

## Evidence References

- WF-7989E1418EA9/07-code-change-plan.json
