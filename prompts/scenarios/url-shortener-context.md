# URL-shortener greenfield scenario context

Build the requested target through the governed workflow and only within the approved target
workspace. Treat the scenario profile as immutable constraints, not as source-code instructions.
Derive the implementation yourself. The target must be an independent FastAPI application with
SQLite, SQLAlchemy 2.x, Alembic, tests, and the required URL creation, resolution, redirect,
expiration, analytics, liveness, and readiness behavior. Do not import the control-plane project,
configure a Git remote, embed credentials, commit database files, or bypass approval gates.
