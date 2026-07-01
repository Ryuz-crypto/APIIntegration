# MTDS 0.2 - Real Data Collection

## Scope

Phase 2 connects the platform to real EdgeConnect APIs through the Compatibility Layer.

## Delivered

- Orchestrator authentication metadata: none, basic, bearer and API key.
- Encrypted credential storage using the application `SECRET_KEY`.
- Real HTTP client with TLS verification, timeout and redirect handling.
- Validation flow based on `orchestrator.version`.
- Inventory discovery based on `orchestrator.inventory.summary`.
- Appliance metric collection based on `appliance.performance`.
- Raw API sample persistence for auditing and troubleshooting.
- UI controls for credential entry, validation, discovery, metrics collection and sample review.

## Acceptance

- Adding an Orchestrator does not require editing files.
- Validation performs a real HTTP request and stores a sample.
- Discovery no longer creates demo records; it parses the real API payload.
- Failed real calls are visible as connection errors and stored as failed samples.
- No EdgeConnect route calls an endpoint outside `app.compatibility`.
