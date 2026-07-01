# ADR 0001 - Compatibility Layer First

## Status

Accepted.

## Context

DashboardAPI-EC must support multiple EdgeConnect API versions and future Swagger/OpenAPI uploads.

## Decision

All EdgeConnect operations are identified by stable operation IDs. The backend resolves the real method and path through profile documents loaded by `app.compatibility`.

## Consequences

- Services can request business operations without knowing endpoint paths.
- API version drift is isolated to profile data.
- Uploaded Swagger documents can generate profile drafts in later phases.
