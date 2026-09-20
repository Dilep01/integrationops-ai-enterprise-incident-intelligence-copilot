# ADR 0003: Separate checkpoints from investigation records

Status: accepted for Phase 4

## Context

LangGraph execution state and user-facing incident records have different access and query patterns. Checkpoints support workflow recovery, while incident reports must support tenant-scoped history, retrieval, evaluation feedback, and reporting.

## Decision

- Persist LangGraph state with a durable SQLite checkpointer in local and portfolio deployments.
- Persist incident requests, reports, and engineer feedback through SQLAlchemy.
- Use SQLite as the zero-configuration local database and PostgreSQL in Docker.
- Use the investigation run ID as the LangGraph thread ID and report identifier.
- Require a tenant identifier for every report lookup and feedback write.
- Expose the console through a separate React application and reverse-proxy `/api` requests to FastAPI.

The tenant header is a demonstration boundary, not authentication. Production deployment requires identity-provider authentication and server-derived tenant claims.

## Consequences

- Local development remains available without Docker.
- PostgreSQL deployment does not change the repository interface.
- Workflow checkpoints can be inspected independently of report history.
- Authentication and database migrations remain required before production use.
