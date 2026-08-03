# Implementation Plan

- Workflow ID: WF-A73E0C8C31C4
- Version: 1

## Structured Evidence

~~~json
{
  "assumptions": [
    "The copied Greenfield short_code uniqueness constraint is reusable."
  ],
  "critical_path": [
    "TASK-001",
    "TASK-002",
    "TASK-003",
    "TASK-004",
    "TASK-005",
    "TASK-006",
    "TASK-007"
  ],
  "execution_order": [
    "TASK-001",
    "TASK-002",
    "TASK-003",
    "TASK-004",
    "TASK-005",
    "TASK-006",
    "TASK-007"
  ],
  "high_risk_tasks": [],
  "implementation_risks": [
    "Concurrent duplicate aliases require precise error mapping."
  ],
  "parallel_groups": [],
  "plan_summary": "Add clarified custom aliases without changing persistence schema.",
  "status": "PLAN_COMPLETE",
  "tasks": [
    {
      "acceptance_criteria_covered": [
        "Approved URL-shortener behavior is implemented."
      ],
      "allowed_paths": [
        "README.md"
      ],
      "dependencies": [],
      "description": "Execute verify repository baseline using governed local tools.",
      "entry_criteria": [
        "All declared dependencies are complete."
      ],
      "exit_criteria": [
        "Owned outputs and validation commands pass."
      ],
      "expected_files": [],
      "parallel_group": null,
      "risk_level": "LOW",
      "task_id": "TASK-001",
      "task_type": "SETUP",
      "title": "Verify repository baseline",
      "validation_commands": [
        "TARGET_IMPORT_CHECK",
        "TARGET_OPENAPI_CHECK"
      ]
    },
    {
      "acceptance_criteria_covered": [
        "Approved URL-shortener behavior is implemented."
      ],
      "allowed_paths": [
        "app/schemas.py",
        "app/short_code_generator.py"
      ],
      "dependencies": [
        "TASK-001"
      ],
      "description": "Execute extend request schema and alias validation using governed local tools.",
      "entry_criteria": [
        "All declared dependencies are complete."
      ],
      "exit_criteria": [
        "Owned outputs and validation commands pass."
      ],
      "expected_files": [
        "app/schemas.py",
        "app/short_code_generator.py"
      ],
      "parallel_group": null,
      "risk_level": "LOW",
      "task_id": "TASK-002",
      "task_type": "IMPLEMENTATION",
      "title": "Extend request schema and alias validation",
      "validation_commands": [
        "TARGET_IMPORT_CHECK"
      ]
    },
    {
      "acceptance_criteria_covered": [
        "Approved URL-shortener behavior is implemented."
      ],
      "allowed_paths": [
        "app/repository.py",
        "app/service.py"
      ],
      "dependencies": [
        "TASK-002"
      ],
      "description": "Execute enhance repository and service alias handling using governed local tools.",
      "entry_criteria": [
        "All declared dependencies are complete."
      ],
      "exit_criteria": [
        "Owned outputs and validation commands pass."
      ],
      "expected_files": [
        "app/service.py"
      ],
      "parallel_group": null,
      "risk_level": "LOW",
      "task_id": "TASK-003",
      "task_type": "IMPLEMENTATION",
      "title": "Enhance repository and service alias handling",
      "validation_commands": [
        "TARGET_IMPORT_CHECK"
      ]
    },
    {
      "acceptance_criteria_covered": [
        "Approved URL-shortener behavior is implemented."
      ],
      "allowed_paths": [
        "app/api/routes.py"
      ],
      "dependencies": [
        "TASK-003"
      ],
      "description": "Execute integrate optional custom alias api endpoint using governed local tools.",
      "entry_criteria": [
        "All declared dependencies are complete."
      ],
      "exit_criteria": [
        "Owned outputs and validation commands pass."
      ],
      "expected_files": [
        "app/api/routes.py"
      ],
      "parallel_group": null,
      "risk_level": "LOW",
      "task_id": "TASK-004",
      "task_type": "INTEGRATION",
      "title": "Integrate optional custom alias API endpoint",
      "validation_commands": [
        "TARGET_IMPORT_CHECK",
        "TARGET_OPENAPI_CHECK"
      ]
    },
    {
      "acceptance_criteria_covered": [
        "Approved URL-shortener behavior is implemented."
      ],
      "allowed_paths": [
        "tests/test_api.py"
      ],
      "dependencies": [
        "TASK-004"
      ],
      "description": "Execute add alias and generated-code regression tests using governed local tools.",
      "entry_criteria": [
        "All declared dependencies are complete."
      ],
      "exit_criteria": [
        "Owned outputs and validation commands pass."
      ],
      "expected_files": [
        "tests/test_api.py"
      ],
      "parallel_group": null,
      "risk_level": "LOW",
      "task_id": "TASK-005",
      "task_type": "TESTING",
      "title": "Add alias and generated-code regression tests",
      "validation_commands": [
        "PYTEST"
      ]
    },
    {
      "acceptance_criteria_covered": [
        "Approved URL-shortener behavior is implemented."
      ],
      "allowed_paths": [
        "README.md",
        "docs"
      ],
      "dependencies": [
        "TASK-005"
      ],
      "description": "Execute update alias release documentation using governed local tools.",
      "entry_criteria": [
        "All declared dependencies are complete."
      ],
      "exit_criteria": [
        "Owned outputs and validation commands pass."
      ],
      "expected_files": [
        "README.md",
        "docs/change-summary.md",
        "docs/known-limitations.md"
      ],
      "parallel_group": null,
      "risk_level": "LOW",
      "task_id": "TASK-006",
      "task_type": "DOCUMENTATION",
      "title": "Update alias release documentation",
      "validation_commands": [
        "RUFF_CHECK"
      ]
    },
    {
      "acceptance_criteria_covered": [
        "Approved URL-shortener behavior is implemented."
      ],
      "allowed_paths": [],
      "dependencies": [
        "TASK-006"
      ],
      "description": "Execute run final validation using governed local tools.",
      "entry_criteria": [
        "All declared dependencies are complete."
      ],
      "exit_criteria": [
        "Owned outputs and validation commands pass."
      ],
      "expected_files": [],
      "parallel_group": null,
      "risk_level": "LOW",
      "task_id": "TASK-007",
      "task_type": "VALIDATION",
      "title": "Run final validation",
      "validation_commands": [
        "TARGET_IMPORT_CHECK",
        "TARGET_OPENAPI_CHECK",
        "RUFF_CHECK",
        "PYTEST",
        "ALEMBIC_UPGRADE_HEAD",
        "ALEMBIC_DOWNGRADE_BASE",
        "ALEMBIC_UPGRADE_HEAD",
        "ALEMBIC_CURRENT"
      ]
    }
  ]
}
~~~

## Evidence References

- WF-A73E0C8C31C4/05-implementation-plan.json
