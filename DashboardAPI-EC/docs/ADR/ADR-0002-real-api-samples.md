# ADR 0002 - Persist Raw API Samples

## Status

Accepted.

## Context

Operators need to prove which EdgeConnect API was called, how long it took and what the source returned.

## Decision

Every real API request can create an `ApiSample` row with operation ID, resolved path, HTTP status, latency, success flag, payload and error information.

## Consequences

- Troubleshooting can inspect source data without re-querying the appliance.
- Widgets can later expose the exact API used.
- Payload retention policy must be enforced in a later phase.
